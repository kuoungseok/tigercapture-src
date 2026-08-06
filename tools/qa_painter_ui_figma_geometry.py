from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import sys
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.painter_ui_figma import (  # noqa: E402
    _figma_document_root,
    _figma_node_stable_id,
    _figma_rotation_degrees,
    _top_level_frames,
    import_figma_payload,
)
from tools.fetch_painter_ui_figma_document_corpus import (  # noqa: E402
    DEFAULT_MANIFEST,
    DEFAULT_OUTPUT_ROOT,
    FigmaCorpusError,
    _safe_relative_path,
)
from tools.qa_painter_ui_figma_document_corpus import (  # noqa: E402
    _load_case_source,
    _load_manifest,
    _verify_case_artifact,
)


DEFAULT_NIGHTLY_MANIFEST = DEFAULT_MANIFEST.with_name("nightly_manifest.json")
_IDENTITY_LINEAR = (1.0, 0.0, 0.0, 1.0)
_AFFINE_EPSILON = 0.0001


def _number(value: object) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _box(value: object) -> dict[str, float] | None:
    if not isinstance(value, Mapping):
        return None
    result = {key: _number(value.get(key)) for key in ("x", "y", "width", "height")}
    if any(item is None for item in result.values()):
        return None
    return {key: float(item) for key, item in result.items() if item is not None}


def _node_linear(node: Mapping[str, Any]) -> tuple[float, float, float, float]:
    transform = node.get("relativeTransform")
    if (
        isinstance(transform, list)
        and len(transform) >= 2
        and isinstance(transform[0], list)
        and isinstance(transform[1], list)
        and len(transform[0]) >= 2
        and len(transform[1]) >= 2
    ):
        values = (
            _number(transform[0][0]),
            _number(transform[0][1]),
            _number(transform[1][0]),
            _number(transform[1][1]),
        )
        if all(value is not None for value in values):
            return tuple(float(value) for value in values)  # type: ignore[return-value]
    rotation = _figma_rotation_degrees(node)
    if abs(rotation) <= _AFFINE_EPSILON:
        return _IDENTITY_LINEAR
    radians = math.radians(rotation)
    cosine = math.cos(radians)
    sine = math.sin(radians)
    return (cosine, -sine, sine, cosine)


def _multiply_linear(
    parent: tuple[float, float, float, float],
    child: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    pa, pc, pb, pd = parent
    ca, cc, cb, cd = child
    return (
        pa * ca + pc * cb,
        pa * cc + pc * cd,
        pb * ca + pd * cb,
        pb * cc + pd * cd,
    )


def _linear_diagnostics(
    transform: tuple[float, float, float, float],
) -> dict[str, Any]:
    a, c, b, d = transform
    scale_x = math.hypot(a, b)
    scale_y = math.hypot(c, d)
    determinant = a * d - b * c
    orthogonality = abs(a * c + b * d) / max(
        _AFFINE_EPSILON,
        scale_x * scale_y,
    )
    non_identity = max(abs(a - 1.0), abs(b), abs(c), abs(d - 1.0)) > _AFFINE_EPSILON
    if determinant <= _AFFINE_EPSILON:
        kind = "reflection_or_degenerate"
    elif orthogonality > _AFFINE_EPSILON:
        kind = "shear"
    elif non_identity:
        kind = "orthogonal_affine"
    else:
        kind = "identity"
    return {
        "kind": kind,
        "matrix": [[a, c], [b, d]],
        "scale_x": scale_x,
        "scale_y": scale_y,
        "determinant": determinant,
        "orthogonality_error": orthogonality,
    }


def _source_geometry_index(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    root = _figma_document_root(payload)
    if root is None:
        raise ValueError("Figma payload has no document root")
    pages = [
        row
        for row in root.get("children", [])
        if isinstance(row, Mapping)
        and str(row.get("type") or "").upper() == "CANVAS"
    ]
    result: dict[str, dict[str, Any]] = {}

    for page in pages:
        for frame in _top_level_frames(page):
            frame_id = _figma_node_stable_id(frame, "artboard")
            frame_box = _box(frame.get("absoluteBoundingBox"))
            frame_linear = _node_linear(frame)

            def visit(
                node: Mapping[str, Any],
                parent_id: str = "",
                parent_linear: tuple[float, float, float, float] = _IDENTITY_LINEAR,
                parent_visible: bool = True,
            ) -> None:
                object_id = _figma_node_stable_id(node)
                effective_linear = _multiply_linear(parent_linear, _node_linear(node))
                effectively_visible = (
                    parent_visible and bool(node.get("visible", True))
                )
                result[object_id] = {
                    "object_id": object_id,
                    "source_node_id": str(node.get("id") or ""),
                    "source_type": str(node.get("type") or "").upper(),
                    "source_name": str(node.get("name") or ""),
                    "node": node,
                    "parent_id": parent_id,
                    "artboard_id": frame_id,
                    "frame_box": frame_box,
                    "source_box": _box(node.get("absoluteBoundingBox")),
                    "source_visible": bool(node.get("visible", True)),
                    "effectively_visible": effectively_visible,
                    "effective_linear": effective_linear,
                    "affine": _linear_diagnostics(effective_linear),
                }
                for child in node.get("children", []):
                    if isinstance(child, Mapping):
                        visit(
                            child,
                            object_id,
                            effective_linear,
                            effectively_visible,
                        )

            if str(frame.get("type") or "").upper() == "COMPONENT":
                visit(frame)
            else:
                for child in frame.get("children", []):
                    if isinstance(child, Mapping):
                        visit(
                            child,
                            "",
                            frame_linear,
                            bool(frame.get("visible", True)),
                        )
    return result


def _rendered_aabb(rect: Mapping[str, float], rotation: float) -> dict[str, float]:
    width = float(rect["width"])
    height = float(rect["height"])
    center_x = float(rect["x"]) + width * 0.5
    center_y = float(rect["y"]) + height * 0.5
    radians = math.radians(float(rotation))
    cosine = abs(math.cos(radians))
    sine = abs(math.sin(radians))
    rendered_width = width * cosine + height * sine
    rendered_height = width * sine + height * cosine
    return {
        "x": center_x - rendered_width * 0.5,
        "y": center_y - rendered_height * 0.5,
        "width": rendered_width,
        "height": rendered_height,
    }


def _rotation_delta(actual: float, expected: float) -> float:
    return (float(actual) - float(expected) + 180.0) % 360.0 - 180.0


def _percentile(values: Iterable[float], percentile: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return 0.0
    index = max(0, min(len(ordered) - 1, math.ceil((len(ordered) - 1) * percentile)))
    return ordered[index]


def _source_constraint_modes(node: Mapping[str, Any]) -> tuple[str, str]:
    constraints = node.get("constraints")
    constraints = constraints if isinstance(constraints, Mapping) else {}
    return (
        str(constraints.get("horizontal") or "MIN").upper(),
        str(constraints.get("vertical") or "MIN").upper(),
    )


def _initial_causes(
    row: Mapping[str, Any],
    source: Mapping[str, Any],
    source_index: Mapping[str, Mapping[str, Any]],
    objects_by_id: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    causes: list[str] = []
    node = source["node"]
    parent_id = str(row.get("parent_id") or "")
    parent_source = source_index.get(parent_id, {})
    parent_node = parent_source.get("node")
    parent_node = parent_node if isinstance(parent_node, Mapping) else {}
    parent_row = objects_by_id.get(parent_id, {})
    parent_layout = parent_row.get("layout")
    parent_layout = parent_layout if isinstance(parent_layout, Mapping) else {}

    source_horizontal, source_vertical = _source_constraint_modes(node)
    constraints = row.get("constraints")
    constraints = constraints if isinstance(constraints, Mapping) else {}
    if (
        source_horizontal == "CENTER"
        or source_vertical == "CENTER"
        or str(constraints.get("horizontal") or "") == "center"
        or str(constraints.get("vertical") or "") == "center"
        or str(parent_node.get("primaryAxisAlignItems") or "").upper() == "CENTER"
        or str(parent_node.get("counterAxisAlignItems") or "").upper() == "CENTER"
    ):
        causes.append("center")
    if (
        str(parent_node.get("layoutWrap") or "").upper() == "WRAP"
        or bool(parent_layout.get("wrap"))
    ):
        causes.append("wrap")
    spacing = _number(parent_node.get("itemSpacing"))
    cross_spacing = _number(parent_node.get("counterAxisSpacing"))
    if (spacing is not None and spacing < 0.0) or (
        cross_spacing is not None and cross_spacing < 0.0
    ):
        causes.append("negative_spacing")
    if str(source.get("affine", {}).get("kind") or "") != "identity":
        causes.append("affine")
    if (
        source_horizontal not in {"", "MIN"}
        or source_vertical not in {"", "MIN"}
        or str(constraints.get("horizontal") or "left") != "left"
        or str(constraints.get("vertical") or "top") != "top"
    ):
        causes.append("constraints")
    return causes


def _exclusion_reason(
    row: Mapping[str, Any],
    source: Mapping[str, Any] | None,
) -> str:
    if source is None:
        return "source_object_not_indexed"
    if source.get("source_box") is None:
        return "source_missing_absolute_bounding_box"
    if source.get("frame_box") is None:
        return "source_artboard_missing_absolute_bounding_box"
    source_box = source.get("source_box")
    source_box = source_box if isinstance(source_box, Mapping) else {}
    if (
        not bool(source.get("effectively_visible", True))
        and (
            float(source_box.get("width") or 0.0) <= 0.0
            or float(source_box.get("height") or 0.0) <= 0.0
        )
    ):
        return "source_hidden_degenerate_bounding_box_nonrendered"
    affine = source.get("affine")
    affine = affine if isinstance(affine, Mapping) else {}
    if affine.get("kind") == "reflection_or_degenerate":
        return "source_affine_reflection_or_degenerate_not_exactly_comparable"
    if affine.get("kind") == "shear":
        return "source_affine_shear_not_exactly_comparable"
    content = row.get("content")
    content = content if isinstance(content, Mapping) else {}
    recovery = content.get("figma_affine_snapshot_geometry")
    recovery = recovery if isinstance(recovery, Mapping) else {}
    status = str(recovery.get("status") or "")
    if status.startswith("blocked_"):
        return "affine_recovery_blocked:" + str(
            recovery.get("reason") or status
        )
    if recovery.get("outer_affine_ignored"):
        return "outer_affine_ignored:" + str(
            recovery.get("outer_affine_reason") or "unknown"
        )
    return ""


def _exclusion_category(reason: str) -> str:
    """Separate explicit source/contract blockers from QA instrumentation loss."""
    known_prefixes = (
        "affine_recovery_blocked:",
        "outer_affine_ignored:",
        "source_affine_",
        "source_missing_absolute_bounding_box",
        "source_artboard_missing_absolute_bounding_box",
        "source_hidden_degenerate_bounding_box_nonrendered",
    )
    return "known_blocked" if str(reason).startswith(known_prefixes) else "unexpected"


def _group_summaries(
    measurements: list[dict[str, Any]],
    excluded: list[dict[str, Any]],
    *,
    key: str,
    classification_drift_px: float,
) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    excluded_groups: Counter[str] = Counter()
    for row in measurements:
        groups[str(row.get(key) or "")].append(row)
    for row in excluded:
        excluded_groups[str(row.get(key) or "")] += 1
    summaries: list[dict[str, Any]] = []
    name_key = "artboard_name" if key == "artboard_id" else "parent_name"
    for group_id in sorted(set(groups) | set(excluded_groups)):
        rows = groups.get(group_id, [])
        drifts = [float(row["drift_px"]) for row in rows]
        cause_counts: Counter[str] = Counter()
        for row in rows:
            if float(row["drift_px"]) > classification_drift_px:
                cause_counts.update(str(cause) for cause in row.get("causes", []))
        exemplar = next(iter(rows), None)
        summaries.append(
            {
                key: group_id,
                "name": str((exemplar or {}).get(name_key) or ""),
                "measured_count": len(rows),
                "drifted_count": sum(
                    value > classification_drift_px for value in drifts
                ),
                "excluded_count": int(excluded_groups[group_id]),
                "max_drift_px": round(max(drifts, default=0.0), 6),
                "p95_drift_px": round(_percentile(drifts, 0.95), 6),
                "cause_counts": dict(sorted(cause_counts.items())),
            }
        )
    return sorted(
        summaries,
        key=lambda row: (-float(row["max_drift_px"]), str(row[key])),
    )


def _evaluate_gate(
    audits: Iterable[Mapping[str, Any]],
    *,
    max_drift_px: float | None,
    max_large_drift_count: int | None,
    max_excluded_count: int | None,
    max_known_blocked_excluded_count: int | None = None,
    max_unexpected_excluded_count: int | None = None,
) -> dict[str, Any]:
    if max_drift_px is None and max_large_drift_count is not None:
        raise ValueError("max_large_drift_count requires max_drift_px")
    enabled = any(
        value is not None
        for value in (
            max_drift_px,
            max_excluded_count,
            max_known_blocked_excluded_count,
            max_unexpected_excluded_count,
        )
    )
    if not enabled:
        return {
            "enabled": False,
            "passed": None,
            "mode": "report_only",
            "violations": [],
        }
    allowed_large = int(max_large_drift_count or 0)
    large_count = 0
    excluded_count = 0
    known_blocked_excluded_count = 0
    unexpected_excluded_count = 0
    maximum = 0.0
    for audit in audits:
        excluded_count += int(audit.get("excluded_count") or 0)
        known_blocked_excluded_count += int(
            audit.get("known_blocked_excluded_count") or 0
        )
        unexpected_excluded_count += int(
            audit.get("unexpected_excluded_count") or 0
        )
        for row in audit.get("object_measurements", []):
            drift = float(row.get("drift_px") or 0.0)
            maximum = max(maximum, drift)
            if max_drift_px is not None and drift > float(max_drift_px):
                large_count += 1
    violations: list[str] = []
    if max_drift_px is not None and large_count > allowed_large:
        violations.append(
            f"large_drift_count:{large_count}>{allowed_large}:threshold={max_drift_px}"
        )
    if max_excluded_count is not None and excluded_count > int(max_excluded_count):
        violations.append(
            f"excluded_count:{excluded_count}>{int(max_excluded_count)}"
        )
    if (
        max_known_blocked_excluded_count is not None
        and known_blocked_excluded_count > int(max_known_blocked_excluded_count)
    ):
        violations.append(
            "known_blocked_excluded_count:"
            f"{known_blocked_excluded_count}>"
            f"{int(max_known_blocked_excluded_count)}"
        )
    if (
        max_unexpected_excluded_count is not None
        and unexpected_excluded_count > int(max_unexpected_excluded_count)
    ):
        violations.append(
            "unexpected_excluded_count:"
            f"{unexpected_excluded_count}>"
            f"{int(max_unexpected_excluded_count)}"
        )
    return {
        "enabled": True,
        "passed": not violations,
        "mode": "enforced",
        "max_drift_px": max_drift_px,
        "max_large_drift_count": allowed_large if max_drift_px is not None else None,
        "max_excluded_count": max_excluded_count,
        "max_known_blocked_excluded_count": max_known_blocked_excluded_count,
        "max_unexpected_excluded_count": max_unexpected_excluded_count,
        "observed_max_drift_px": round(maximum, 6),
        "observed_large_drift_count": large_count,
        "observed_excluded_count": excluded_count,
        "observed_known_blocked_excluded_count": known_blocked_excluded_count,
        "observed_unexpected_excluded_count": unexpected_excluded_count,
        "violations": violations,
    }


def measure_figma_geometry(
    payload: Mapping[str, Any],
    document: Mapping[str, Any],
    *,
    classification_drift_px: float = 0.5,
    resolved_geometry: Mapping[str, Mapping[str, float]] | None = None,
    max_drift_px: float | None = None,
    max_large_drift_count: int | None = None,
    max_excluded_count: int | None = None,
    max_known_blocked_excluded_count: int | None = None,
    max_unexpected_excluded_count: int | None = None,
) -> dict[str, Any]:
    """Measure resolved Painter geometry against Figma snapshot AABBs."""
    classification_drift_px = float(classification_drift_px)
    if classification_drift_px < 0.0:
        raise ValueError("classification_drift_px must be non-negative")
    source_index = _source_geometry_index(payload)
    objects = [row for row in document.get("objects", []) if isinstance(row, Mapping)]
    objects_by_id = {str(row.get("id") or ""): row for row in objects}
    artboards_by_id = {
        str(row.get("id") or ""): row
        for row in document.get("artboards", [])
        if isinstance(row, Mapping)
    }
    if resolved_geometry is None:
        from app.painter_ui_constraints import resolve_ui_constraints

        resolved_geometry = resolve_ui_constraints(document)

    measurements: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for row in objects:
        object_id = str(row.get("id") or "")
        source = source_index.get(object_id)
        artboard_id = str(row.get("artboard_id") or "")
        parent_id = str(row.get("parent_id") or "")
        parent = objects_by_id.get(parent_id, {})
        artboard = artboards_by_id.get(artboard_id, {})
        common = {
            "object_id": object_id,
            "object_name": str(row.get("name") or ""),
            "kind": str(row.get("kind") or ""),
            "parent_id": parent_id,
            "parent_name": str(parent.get("name") or "Artboard root"),
            "artboard_id": artboard_id,
            "artboard_name": str(artboard.get("name") or ""),
            "source_node_id": str((source or {}).get("source_node_id") or ""),
        }
        reason = _exclusion_reason(row, source)
        actual_rect = (resolved_geometry or {}).get(object_id)
        if not reason and not isinstance(actual_rect, Mapping):
            reason = "resolved_geometry_missing"
        if reason:
            excluded.append(
                {
                    **common,
                    "reason": reason,
                    "category": _exclusion_category(reason),
                }
            )
            continue
        assert source is not None
        source_box = source["source_box"]
        frame_box = source["frame_box"]
        expected = {
            "x": float(source_box["x"]) - float(frame_box["x"]),
            "y": float(source_box["y"]) - float(frame_box["y"]),
            "width": float(source_box["width"]),
            "height": float(source_box["height"]),
        }
        actual_values = {
            key: _number(actual_rect.get(key))
            for key in ("x", "y", "width", "height")
        }
        if any(value is None for value in actual_values.values()):
            excluded.append(
                {
                    **common,
                    "reason": "resolved_geometry_non_finite",
                    "category": "unexpected",
                }
            )
            continue
        actual = {
            key: float(value)
            for key, value in actual_values.items()
            if value is not None
        }
        rotation = float(_number(row.get("rotation")) or 0.0)
        rendered = _rendered_aabb(actual, rotation)
        expected_center = (
            expected["x"] + expected["width"] * 0.5,
            expected["y"] + expected["height"] * 0.5,
        )
        actual_center = (
            rendered["x"] + rendered["width"] * 0.5,
            rendered["y"] + rendered["height"] * 0.5,
        )
        edges = {
            "left": rendered["x"] - expected["x"],
            "top": rendered["y"] - expected["y"],
            "right": (
                rendered["x"] + rendered["width"]
                - expected["x"]
                - expected["width"]
            ),
            "bottom": (
                rendered["y"] + rendered["height"]
                - expected["y"]
                - expected["height"]
            ),
        }
        node = source["node"]
        content = row.get("content")
        content = content if isinstance(content, Mapping) else {}
        affine_recovery = content.get("figma_affine_snapshot_geometry")
        affine_recovery = (
            affine_recovery if isinstance(affine_recovery, Mapping) else {}
        )
        expected_rotation = float(
            _number(affine_recovery.get("rotation"))
            if _number(affine_recovery.get("rotation")) is not None
            else (_number(node.get("rotation")) or 0.0)
        )
        measurement = {
            **common,
            "source_type": str(source.get("source_type") or ""),
            "expected_aabb": expected,
            "resolved_rect": actual,
            "rendered_aabb": rendered,
            "center_delta": {
                "x": actual_center[0] - expected_center[0],
                "y": actual_center[1] - expected_center[1],
                "distance": math.hypot(
                    actual_center[0] - expected_center[0],
                    actual_center[1] - expected_center[1],
                ),
            },
            "size_delta": {
                "width": rendered["width"] - expected["width"],
                "height": rendered["height"] - expected["height"],
            },
            "edge_delta": edges,
            "rotation": {
                "expected_degrees": expected_rotation,
                "actual_degrees": rotation,
                "delta_degrees": _rotation_delta(rotation, expected_rotation),
            },
            "drift_px": max(abs(value) for value in edges.values()),
            "causes": _initial_causes(row, source, source_index, objects_by_id),
        }
        measurements.append(measurement)

    measurement_by_id = {str(row["object_id"]): row for row in measurements}
    children_by_parent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for measurement in measurements:
        if measurement["parent_id"]:
            children_by_parent[str(measurement["parent_id"])].append(measurement)
    reverse_order_parents: set[str] = set()
    for parent_id, children in children_by_parent.items():
        parent_source = source_index.get(parent_id, {})
        parent_node = parent_source.get("node")
        parent_node = parent_node if isinstance(parent_node, Mapping) else {}
        layout_mode = str(parent_node.get("layoutMode") or "").upper()
        if layout_mode not in {"HORIZONTAL", "VERTICAL"} or len(children) < 2:
            continue
        axis = "x" if layout_mode == "HORIZONTAL" else "y"
        size = "width" if layout_mode == "HORIZONTAL" else "height"
        expected_order = sorted(
            children,
            key=lambda item: (
                float(item["expected_aabb"][axis])
                + float(item["expected_aabb"][size]) * 0.5,
                str(item["object_id"]),
            ),
        )
        actual_order = sorted(
            children,
            key=lambda item: (
                float(item["rendered_aabb"][axis])
                + float(item["rendered_aabb"][size]) * 0.5,
                str(item["object_id"]),
            ),
        )
        expected_ids = [str(item["object_id"]) for item in expected_order]
        actual_ids = [str(item["object_id"]) for item in actual_order]
        if actual_ids == list(reversed(expected_ids)) and actual_ids != expected_ids:
            reverse_order_parents.add(parent_id)

    for measurement in measurements:
        parent_id = str(measurement["parent_id"])
        if parent_id in reverse_order_parents:
            measurement["causes"].append("reverse_order")
        parent_measurement = measurement_by_id.get(parent_id)
        if (
            parent_measurement is not None
            and float(parent_measurement["drift_px"]) > classification_drift_px
        ):
            measurement["causes"].append("parent_drift")
        if (
            float(measurement["drift_px"]) > classification_drift_px
            and not measurement["causes"]
        ):
            measurement["causes"].append("unclassified")
        measurement["causes"] = sorted(set(measurement["causes"]))

    drifted = [
        row
        for row in measurements
        if float(row["drift_px"]) > classification_drift_px
    ]
    causes: Counter[str] = Counter()
    for row in drifted:
        causes.update(str(cause) for cause in row["causes"])
    excluded_reasons = Counter(str(row["reason"]) for row in excluded)
    excluded_categories = Counter(str(row["category"]) for row in excluded)
    drift_values = [float(row["drift_px"]) for row in measurements]
    report: dict[str, Any] = {
        "schema": "tigercapture.painter.figma_geometry_measurement.v1",
        "classification_drift_px": classification_drift_px,
        "source_object_count": len(source_index),
        "document_object_count": len(objects),
        "measured_count": len(measurements),
        "drifted_count": len(drifted),
        "excluded_count": len(excluded),
        "known_blocked_excluded_count": int(excluded_categories["known_blocked"]),
        "unexpected_excluded_count": int(excluded_categories["unexpected"]),
        "max_drift_px": round(max(drift_values, default=0.0), 6),
        "p50_drift_px": round(_percentile(drift_values, 0.50), 6),
        "p95_drift_px": round(_percentile(drift_values, 0.95), 6),
        "p99_drift_px": round(_percentile(drift_values, 0.99), 6),
        "cause_counts": dict(sorted(causes.items())),
        "excluded_reason_counts": dict(sorted(excluded_reasons.items())),
        "excluded_category_counts": dict(sorted(excluded_categories.items())),
        "by_artboard": _group_summaries(
            measurements,
            excluded,
            key="artboard_id",
            classification_drift_px=classification_drift_px,
        ),
        "by_parent": _group_summaries(
            measurements,
            excluded,
            key="parent_id",
            classification_drift_px=classification_drift_px,
        ),
        "object_measurements": measurements,
        "drifts": sorted(
            drifted,
            key=lambda row: (-float(row["drift_px"]), str(row["object_id"])),
        ),
        "excluded_with_reason": excluded,
    }
    report["gate"] = _evaluate_gate(
        [report],
        max_drift_px=max_drift_px,
        max_large_drift_count=max_large_drift_count,
        max_excluded_count=max_excluded_count,
        max_known_blocked_excluded_count=max_known_blocked_excluded_count,
        max_unexpected_excluded_count=max_unexpected_excluded_count,
    )
    return report


def run_geometry_corpus(
    manifest_paths: Iterable[str | Path],
    assets_root: str | Path,
    output: str | Path,
    *,
    case_ids: set[str] | None = None,
    classification_drift_px: float = 0.5,
    max_drift_px: float | None = None,
    max_large_drift_count: int | None = None,
    max_excluded_count: int | None = None,
    max_known_blocked_excluded_count: int | None = None,
    max_unexpected_excluded_count: int | None = None,
) -> dict[str, Any]:
    manifests = [Path(path).expanduser().resolve() for path in manifest_paths]
    if not manifests:
        raise FigmaCorpusError("At least one manifest is required")
    assets_root = Path(assets_root).expanduser().resolve()
    output = Path(output).expanduser().resolve()
    manifest_rows = [(path, _load_manifest(path)) for path in manifests]
    known = {
        str(item["id"])
        for _path, manifest in manifest_rows
        for item in manifest["cases"]
    }
    selected = set(case_ids or ())
    if selected - known:
        raise FigmaCorpusError(
            f"Unknown corpus case ids: {', '.join(sorted(selected - known))}"
        )

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for manifest_path, manifest in manifest_rows:
        for item in manifest["cases"]:
            case_id = str(item["id"])
            if case_id in seen or (selected and case_id not in selected):
                continue
            seen.add(case_id)
            artifact = item["artifact"]
            source_path = (
                assets_root / _safe_relative_path(artifact["relative_path"])
            ).resolve()
            case: dict[str, Any] = {
                "id": case_id,
                "title": str(item.get("title") or case_id),
                "manifest": str(manifest_path),
                "source_path": str(source_path),
            }
            try:
                _verify_case_artifact(source_path, artifact)
                payload, image_paths, _source_details = _load_case_source(source_path)
                document, import_report = import_figma_payload(
                    payload,
                    source=str(source_path),
                    image_paths=image_paths,
                )
                audit = measure_figma_geometry(
                    payload,
                    document,
                    classification_drift_px=classification_drift_px,
                )
                case.update(
                    {
                        "ok": True,
                        "error": "",
                        "import": {
                            "artboard_count": int(import_report["artboard_count"]),
                            "object_count": int(import_report["object_count"]),
                            "warning_count": len(import_report.get("warnings", [])),
                        },
                        "geometry": audit,
                    }
                )
            except Exception as exc:
                case.update(
                    {
                        "ok": False,
                        "error": f"{type(exc).__name__}: {exc}",
                        "geometry": {},
                    }
                )
            rows.append(case)

    audits = [row["geometry"] for row in rows if row.get("ok")]
    gate = _evaluate_gate(
        audits,
        max_drift_px=max_drift_px,
        max_large_drift_count=max_large_drift_count,
        max_excluded_count=max_excluded_count,
        max_known_blocked_excluded_count=max_known_blocked_excluded_count,
        max_unexpected_excluded_count=max_unexpected_excluded_count,
    )
    cause_totals: Counter[str] = Counter()
    exclusion_totals: Counter[str] = Counter()
    for audit in audits:
        cause_totals.update(audit.get("cause_counts", {}))
        exclusion_totals.update(audit.get("excluded_reason_counts", {}))
    processing_ok = bool(rows) and all(bool(row.get("ok")) for row in rows)
    report = {
        "schema": "tigercapture.painter.figma_geometry_corpus_report.v1",
        "manifests": [str(path) for path in manifests],
        "assets_root": str(assets_root),
        "classification_drift_px": float(classification_drift_px),
        "case_count": len(rows),
        "processing_ok": processing_ok,
        "measured_count": sum(int(audit.get("measured_count") or 0) for audit in audits),
        "drifted_count": sum(int(audit.get("drifted_count") or 0) for audit in audits),
        "excluded_count": sum(int(audit.get("excluded_count") or 0) for audit in audits),
        "known_blocked_excluded_count": sum(
            int(audit.get("known_blocked_excluded_count") or 0)
            for audit in audits
        ),
        "unexpected_excluded_count": sum(
            int(audit.get("unexpected_excluded_count") or 0)
            for audit in audits
        ),
        "max_drift_px": round(
            max((float(audit.get("max_drift_px") or 0.0) for audit in audits), default=0.0),
            6,
        ),
        "cause_totals": dict(sorted(cause_totals.items())),
        "excluded_reason_totals": dict(sorted(exclusion_totals.items())),
        "threshold_suggestions": {
            "regression_ratchet": {
                "max_drift_px": 1.0,
                "max_large_drift_count": sum(
                    float(row.get("drift_px") or 0.0) > 1.0
                    for audit in audits
                    for row in audit.get("object_measurements", [])
                ),
                "max_known_blocked_excluded_count": sum(
                    int(audit.get("known_blocked_excluded_count") or 0)
                    for audit in audits
                ),
                "max_unexpected_excluded_count": 0,
                "purpose": "freeze the measured baseline while fixes land",
            },
            "m1_target": {
                "max_drift_px": 1.0,
                "max_large_drift_count": 0,
                "max_known_blocked_excluded_count": sum(
                    int(audit.get("known_blocked_excluded_count") or 0)
                    for audit in audits
                ),
                "max_unexpected_excluded_count": 0,
                "purpose": (
                    "one-pixel fidelity with zero instrumentation exclusions; "
                    "explicit source/contract blockers may remain at or below baseline"
                ),
            },
        },
        "gate": gate,
        "passed": processing_ok and (gate["passed"] is not False),
        "cases": rows,
    }
    output.mkdir(parents=True, exist_ok=True)
    report_path = output / "figma_geometry_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    report["report_path"] = str(report_path)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Measure resolved Painter UI geometry against pinned Figma REST snapshots."
        )
    )
    parser.add_argument("--manifest", action="append", default=[])
    parser.add_argument("--assets-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument(
        "--output",
        default=str(ROOT / "debugCapture" / "painter_ui_figma_geometry"),
    )
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--classification-drift-px", type=float, default=0.5)
    parser.add_argument(
        "--max-drift-px",
        type=float,
        default=None,
        help="Enable the CI gate and classify measurements above this drift as large.",
    )
    parser.add_argument(
        "--max-large-drift-count",
        type=int,
        default=None,
        help="Maximum large-drift objects across the selected corpus (default 0).",
    )
    parser.add_argument(
        "--max-excluded-count",
        type=int,
        default=None,
        help="Optional CI cap for affine/shear/unmeasurable exclusions.",
    )
    parser.add_argument(
        "--max-known-blocked-excluded-count",
        type=int,
        default=None,
        help="CI cap for explicit source/affine contract blockers.",
    )
    parser.add_argument(
        "--max-unexpected-excluded-count",
        type=int,
        default=None,
        help="CI cap for missing mappings or non-finite resolved geometry.",
    )
    args = parser.parse_args()
    manifests = args.manifest or [
        str(DEFAULT_MANIFEST),
        str(DEFAULT_NIGHTLY_MANIFEST),
    ]
    try:
        report = run_geometry_corpus(
            manifests,
            args.assets_root,
            args.output,
            case_ids=set(args.case),
            classification_drift_px=args.classification_drift_px,
            max_drift_px=args.max_drift_px,
            max_large_drift_count=args.max_large_drift_count,
            max_excluded_count=args.max_excluded_count,
            max_known_blocked_excluded_count=(
                args.max_known_blocked_excluded_count
            ),
            max_unexpected_excluded_count=args.max_unexpected_excluded_count,
        )
    except (FigmaCorpusError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    print(
        json.dumps(
            {
                "ok": report["passed"],
                "case_count": report["case_count"],
                "measured_count": report["measured_count"],
                "drifted_count": report["drifted_count"],
                "excluded_count": report["excluded_count"],
                "known_blocked_excluded_count": report[
                    "known_blocked_excluded_count"
                ],
                "unexpected_excluded_count": report[
                    "unexpected_excluded_count"
                ],
                "max_drift_px": report["max_drift_px"],
                "gate": report["gate"],
                "report": report["report_path"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
