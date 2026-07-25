from __future__ import annotations

import math
import random
import uuid
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image


STUDY_SCHEMA = "tigerstudio.painter.ai_study.v1"

PHASE_PRESETS: dict[str, dict[str, Any]] = {
    "underpaint": {
        "step": 24,
        "width": 28.0,
        "length": 92.0,
        "style": "hard_flat",
        "opacity": 248,
        "density": 1.0,
        "edge_bias": 0.0,
        "material": False,
    },
    "forms": {
        "step": 13,
        "width": 12.0,
        "length": 48.0,
        "style": "gouache_flat",
        "opacity": 240,
        "density": 0.72,
        "edge_bias": 0.22,
        "material": False,
    },
    "detail": {
        "step": 7,
        "width": 5.0,
        "length": 24.0,
        "style": "filbert_oil",
        "opacity": 220,
        "density": 0.08,
        "edge_bias": 0.78,
        "material": False,
    },
    "contour": {
        "step": 4,
        "width": 1.25,
        "length": 10.0,
        "style": "rigger_oil",
        "opacity": 205,
        "density": 0.0,
        "edge_bias": 0.94,
        "material": False,
    },
    "accent": {
        "step": 6,
        "width": 3.0,
        "length": 14.0,
        "style": "palette_knife",
        "opacity": 242,
        "density": 0.0,
        "edge_bias": 0.38,
        "material": True,
    },
}


def analyze_reference(
    path: str | Path,
    *,
    target_width: int = 800,
    max_regions: int = 12,
    seed: int = 240725,
    focus_regions: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    source_path = Path(path).expanduser().resolve()
    if not source_path.is_file():
        raise ValueError(f"Painter study reference does not exist: {source_path}")
    image = Image.open(source_path).convert("RGB")
    width = max(256, min(1600, int(target_width or 800)))
    height = max(256, round(width * image.height / max(1, image.width)))
    image = image.resize((width, height), Image.Resampling.LANCZOS)
    rgb = np.asarray(image, dtype=np.uint8)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    flow_gx = cv2.GaussianBlur(gx, (0, 0), 4.0)
    flow_gy = cv2.GaussianBlur(gy, (0, 0), 4.0)
    magnitude = cv2.magnitude(gx, gy)
    edge_scale = max(1e-6, float(np.percentile(magnitude, 97)))
    edge = np.clip(magnitude / edge_scale, 0.0, 1.0)
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    labels, centers = _cluster_regions(lab, max_regions=max_regions, seed=seed)
    labels_smooth = cv2.medianBlur(labels.astype(np.uint8), 7).astype(np.int32)
    session_id = f"paint-study-{uuid.uuid4().hex[:12]}"
    runtime = {
        "session_id": session_id,
        "reference_path": str(source_path),
        "width": width,
        "height": height,
        "rgb": rgb,
        "gray": gray,
        "gx": gx,
        "gy": gy,
        "flow_gx": flow_gx,
        "flow_gy": flow_gy,
        "edge": edge,
        "labels": labels,
        "labels_smooth": labels_smooth,
        "centers_lab": centers,
        "seed": int(seed),
        "generated_layers": [],
        "generated_layer_history": [],
        "generated_layer_history": [],
        "stroke_count": 0,
        "last_comparison": {},
        "baked_reference_pixels": False,
        "timings": [],
        "timings": [],
        "focus_regions": _normalize_focus_regions(focus_regions),
    }
    report = {
        "schema": STUDY_SCHEMA,
        "session_id": session_id,
        "reference_path": str(source_path),
        "canvas": {"width": width, "height": height},
        "edge_coverage": round(float(np.mean(edge >= 0.22)), 6),
        "luminance": {
            "mean": round(float(np.mean(gray)) / 255.0, 6),
            "p05": round(float(np.percentile(gray, 5)) / 255.0, 6),
            "p95": round(float(np.percentile(gray, 95)) / 255.0, 6),
        },
        "region_count": int(len(centers)),
        "seed": int(seed),
        "focus_regions": list(runtime["focus_regions"]),
    }
    return runtime, report


def segment_report(runtime: dict[str, Any]) -> dict[str, Any]:
    labels = np.asarray(runtime["labels"])
    rgb = np.asarray(runtime["rgb"])
    rows: list[dict[str, Any]] = []
    total = max(1, labels.size)
    for label in sorted(int(value) for value in np.unique(labels)):
        mask = labels == label
        ys, xs = np.where(mask)
        if not len(xs):
            continue
        color = np.mean(rgb[mask], axis=0)
        rows.append(
            {
                "region_id": f"region-{label:02d}",
                "coverage": round(float(mask.sum()) / total, 6),
                "bbox_norm": [
                    round(float(xs.min()) / runtime["width"], 6),
                    round(float(ys.min()) / runtime["height"], 6),
                    round(float(xs.max() + 1) / runtime["width"], 6),
                    round(float(ys.max() + 1) / runtime["height"], 6),
                ],
                "mean_rgb": [int(round(value)) for value in color],
                "edge_density": round(float(np.mean(runtime["edge"][mask])), 6),
            }
        )
    rows.sort(key=lambda row: row["coverage"], reverse=True)
    return {
        "schema": STUDY_SCHEMA,
        "session_id": runtime["session_id"],
        "regions": rows,
    }


def generate_phase_strokes(
    runtime: dict[str, Any],
    *,
    phase: str,
    layer_id: str,
    max_strokes: int = 5000,
    seed_offset: int = 0,
) -> list[Any]:
    from app.drawing import Stroke

    key = str(phase or "").strip().casefold()
    if key not in PHASE_PRESETS:
        raise ValueError(f"Unknown Painter study phase: {phase}")
    preset = PHASE_PRESETS[key]
    rgb = np.asarray(runtime["rgb"])
    gx = np.asarray(runtime["gx"])
    gy = np.asarray(runtime["gy"])
    flow_gx = np.asarray(runtime.get("flow_gx", gx))
    flow_gy = np.asarray(runtime.get("flow_gy", gy))
    edge = np.asarray(runtime["edge"])
    height, width = rgb.shape[:2]
    if key == "underpaint":
        return _generate_region_underpaint(
            runtime,
            layer_id=layer_id,
            max_strokes=max_strokes,
            seed_offset=seed_offset,
        )
    blur_sigma = {
        "underpaint": 9.0,
        "forms": 4.0,
        "detail": 1.4,
        "contour": 0.8,
        "accent": 0.8,
    }[key]
    color_source = cv2.GaussianBlur(rgb, (0, 0), blur_sigma)
    step = int(preset["step"])
    rng = random.Random(int(runtime["seed"]) + int(seed_offset) + sum(map(ord, key)))
    candidates: list[tuple[float, int, int]] = []
    candidate_keys: set[tuple[int, int]] = set()
    margin = max(2, step // 2)
    for y in range(margin, height - margin, step):
        for x in range(margin, width - margin, step):
            local_edge = float(edge[y, x])
            probability = min(
                1.0,
                float(preset["density"]) + local_edge * float(preset["edge_bias"]),
            )
            if rng.random() <= probability:
                importance = local_edge + rng.random() * 0.12
                candidates.append((importance, x, y))
                candidate_keys.add((x, y))
    if key in {"detail", "contour", "accent"}:
        focus_step = max(2, step // 2)
        for focus in runtime.get("focus_regions") or []:
            x0, y0, x1, y1 = focus["bbox_norm"]
            priority = float(focus.get("priority", 1.0))
            for y in range(max(margin, int(y0 * height)), min(height - margin, int(y1 * height)), focus_step):
                for x in range(max(margin, int(x0 * width)), min(width - margin, int(x1 * width)), focus_step):
                    if (x, y) in candidate_keys:
                        continue
                    local_edge = float(edge[y, x])
                    importance = local_edge + 0.5 * priority + rng.random() * 0.12
                    candidates.append((importance, x, y))
                    candidate_keys.add((x, y))
    candidates.sort(reverse=True)
    if len(candidates) > max(1, int(max_strokes)):
        candidates = candidates[: max(1, int(max_strokes))]
    strokes: list[Stroke] = []
    for _, x, y in candidates:
        local_edge = float(edge[y, x])
        direction_x = float(flow_gx[y, x])
        direction_y = float(flow_gy[y, x])
        angle = math.atan2(direction_y, direction_x) + math.pi * 0.5
        if local_edge < 0.04:
            if math.hypot(direction_x, direction_y) < 0.5:
                angle = 0.0
        length = float(preset["length"]) * rng.uniform(0.74, 1.22)
        half = length * 0.5
        dx, dy = math.cos(angle) * half, math.sin(angle) * half
        bend = rng.uniform(-0.10, 0.10) * length
        control = (x - math.sin(angle) * bend, y + math.cos(angle) * bend)
        points = _quadratic_points(
            (x - dx, y - dy),
            control,
            (x + dx, y + dy),
            width=width,
            height=height,
        )
        color = tuple(int(value) for value in color_source[y, x])
        focus_weight = _focus_weight(runtime.get("focus_regions") or [], x / width, y / height)
        size_scale = 0.58 if focus_weight > 0.0 and key in {"detail", "contour"} else 1.0
        peak = rng.uniform(0.88, 1.0)
        pressures = [max(0.54, peak - abs(index - 5) * 0.04) for index in range(11)]
        material = bool(preset["material"])
        strokes.append(
            Stroke(
                points=points,
                color=color,
                opacity=int(preset["opacity"]),
                width_px=float(preset["width"]) * size_scale * rng.uniform(0.82, 1.16),
                brush_style=str(preset["style"]),
                brush_hardness=78,
                brush_spacing=10,
                brush_angle=int(math.degrees(angle)) % 360,
                brush_roundness=58,
                layer_id=str(layer_id),
                source_tool=f"ai_study_{key}",
                brush_engine_version=2,
                point_pressure=pressures,
                point_tilt=[0.5] * 11,
                point_rotation=[0.5] * 11,
                point_load=[1.0 - index * 0.038 for index in range(11)],
                bristle_count=18 if "oil" in str(preset["style"]) else 8,
                brush_seed=rng.randrange(1, 2**31 - 1),
                load_depletion=0.32,
                material_enabled=material,
                material_load=0.48 if material else 0.0,
                material_thickness=0.36 if material else 0.0,
                material_wetness=0.18 if material else 0.0,
                material_gloss=0.22 if material else 0.0,
                material_roughness=0.58,
            )
        )
    return strokes


def _generate_region_underpaint(
    runtime: dict[str, Any],
    *,
    layer_id: str,
    max_strokes: int,
    seed_offset: int,
) -> list[Any]:
    from app.drawing import Stroke

    rgb = cv2.GaussianBlur(np.asarray(runtime["rgb"]), (0, 0), 2.2)
    labels = np.asarray(runtime.get("labels_smooth", runtime["labels"]))
    height, width = labels.shape
    row_step = 4
    rows: list[tuple[int, int, int, int]] = []
    for y in range(1, height - 1, row_step):
        start = 0
        current = int(labels[y, 0])
        for x in range(1, width + 1):
            value = int(labels[y, x]) if x < width else -1
            if value != current:
                if x - start >= 2:
                    rows.append((x - start, y, start, x - 1))
                start = x
                current = value
    rows.sort(reverse=True)
    rows = rows[: max(1, int(max_strokes))]
    rng = random.Random(int(runtime["seed"]) + int(seed_offset) + 4411)
    strokes: list[Stroke] = []
    for _, y, x0, x1 in rows:
        segment = rgb[y, x0 : x1 + 1]
        color = tuple(int(value) for value in np.mean(segment, axis=0))
        normalized_y = y / max(1, height)
        points = [
            (x0 / max(1, width), normalized_y),
            ((x0 * 0.75 + x1 * 0.25) / max(1, width), normalized_y),
            ((x0 + x1) * 0.5 / max(1, width), normalized_y),
            ((x0 * 0.25 + x1 * 0.75) / max(1, width), normalized_y),
            (x1 / max(1, width), normalized_y),
        ]
        strokes.append(
            Stroke(
                points=points,
                color=color,
                opacity=255,
                width_px=5.2,
                brush_style="hard_flat",
                brush_hardness=92,
                brush_spacing=6,
                brush_angle=0,
                brush_roundness=45,
                layer_id=str(layer_id),
                source_tool="ai_study_underpaint",
                brush_engine_version=2,
                point_pressure=[1.0] * 5,
                point_tilt=[0.5] * 5,
                point_rotation=[0.5] * 5,
                point_load=[1.0, 0.96, 0.92, 0.88, 0.84],
                bristle_count=6,
                brush_seed=rng.randrange(1, 2**31 - 1),
                load_depletion=0.12,
            )
        )
    return strokes


def compare_reference_to_render(
    runtime: dict[str, Any],
    rendered: Image.Image | np.ndarray,
) -> dict[str, Any]:
    reference = np.asarray(runtime["rgb"], dtype=np.uint8)
    if isinstance(rendered, Image.Image):
        candidate = np.asarray(
            rendered.convert("RGB").resize(
                (runtime["width"], runtime["height"]),
                Image.Resampling.LANCZOS,
            ),
            dtype=np.uint8,
        )
    else:
        candidate = np.asarray(rendered, dtype=np.uint8)
        if candidate.shape[:2] != reference.shape[:2]:
            candidate = cv2.resize(
                candidate,
                (runtime["width"], runtime["height"]),
                interpolation=cv2.INTER_LANCZOS4,
            )
    absolute = np.abs(reference.astype(np.float32) - candidate.astype(np.float32))
    ref_gray = cv2.cvtColor(reference, cv2.COLOR_RGB2GRAY).astype(np.float32)
    out_gray = cv2.cvtColor(candidate, cv2.COLOR_RGB2GRAY).astype(np.float32)
    correlation = float(np.corrcoef(ref_gray.ravel(), out_gray.ravel())[0, 1])
    if not math.isfinite(correlation):
        correlation = 0.0
    ref_structure = cv2.GaussianBlur(reference, (0, 0), 2.2)
    out_structure = cv2.GaussianBlur(candidate, (0, 0), 2.2)
    ref_edges = cv2.Canny(ref_structure, 45, 110) > 0
    out_edges = cv2.Canny(out_structure, 45, 110) > 0
    intersection = int(np.logical_and(ref_edges, out_edges).sum())
    union = int(np.logical_or(ref_edges, out_edges).sum())
    kernel = np.ones((5, 5), np.uint8)
    ref_dilated = cv2.dilate(ref_edges.astype(np.uint8), kernel) > 0
    out_dilated = cv2.dilate(out_edges.astype(np.uint8), kernel) > 0
    recall = float(np.logical_and(ref_edges, out_dilated).sum()) / max(1, int(ref_edges.sum()))
    precision = float(np.logical_and(out_edges, ref_dilated).sum()) / max(1, int(out_edges.sum()))
    edge_f1 = 2.0 * precision * recall / max(1e-6, precision + recall)
    focus_rows: list[dict[str, Any]] = []
    for focus in runtime.get("focus_regions") or []:
        x0, y0, x1, y1 = focus["bbox_norm"]
        left, top = int(x0 * runtime["width"]), int(y0 * runtime["height"])
        right, bottom = int(x1 * runtime["width"]), int(y1 * runtime["height"])
        ref_crop = reference[top:bottom, left:right]
        out_crop = candidate[top:bottom, left:right]
        if not ref_crop.size or not out_crop.size:
            continue
        focus_rows.append(
            {
                "id": focus["id"],
                "priority": focus["priority"],
                "mean_absolute_error": round(
                    float(np.mean(np.abs(ref_crop.astype(np.float32) - out_crop.astype(np.float32)))),
                    6,
                ),
            }
        )
    report = {
        "schema": STUDY_SCHEMA,
        "session_id": runtime["session_id"],
        "mean_absolute_error": round(float(np.mean(absolute)), 6),
        "p95_absolute_error": round(float(np.percentile(absolute, 95)), 6),
        "luminance_correlation": round(correlation, 6),
        "edge_iou": round(intersection / max(1, union), 6),
        "structural_edge_f1": round(edge_f1, 6),
        "focus_regions": focus_rows,
    }
    runtime["last_comparison"] = report
    runtime["error_map"] = np.mean(absolute, axis=2)
    return report


def generate_refinement_strokes(
    runtime: dict[str, Any],
    *,
    layer_id: str,
    max_strokes: int = 5000,
    seed_offset: int = 0,
) -> list[Any]:
    from app.drawing import Stroke

    error_map = runtime.get("error_map")
    if error_map is None:
        raise ValueError("Painter study compare_render must run before refinement")
    error = np.asarray(error_map, dtype=np.float32)
    scale = max(1e-6, float(np.percentile(error, 95)))
    normalized_error = np.clip(error / scale, 0.0, 1.0)
    rgb = cv2.GaussianBlur(np.asarray(runtime["rgb"]), (0, 0), 0.7)
    flow_gx = np.asarray(runtime["flow_gx"])
    flow_gy = np.asarray(runtime["flow_gy"])
    height, width = normalized_error.shape
    candidates: list[tuple[float, int, int]] = []
    rng = random.Random(int(runtime["seed"]) + int(seed_offset) + 9109)
    for y in range(2, height - 2, 3):
        for x in range(2, width - 2, 3):
            focus = _focus_weight(runtime.get("focus_regions") or [], x / width, y / height)
            score = float(normalized_error[y, x]) + focus * 0.24
            if score >= 0.42:
                candidates.append((score + rng.random() * 0.04, x, y))
    candidates.sort(reverse=True)
    strokes: list[Stroke] = []
    for _, x, y in candidates[: max(1, int(max_strokes))]:
        angle = math.atan2(float(flow_gy[y, x]), float(flow_gx[y, x])) + math.pi * 0.5
        length = rng.uniform(6.0, 10.0)
        dx, dy = math.cos(angle) * length * 0.5, math.sin(angle) * length * 0.5
        points = _quadratic_points(
            (x - dx, y - dy),
            (x, y),
            (x + dx, y + dy),
            width=width,
            height=height,
        )
        strokes.append(
            Stroke(
                points=points,
                color=tuple(int(value) for value in rgb[y, x]),
                opacity=218,
                width_px=rng.uniform(1.6, 2.5),
                brush_style="filbert_oil",
                brush_hardness=72,
                brush_spacing=7,
                brush_angle=int(math.degrees(angle)) % 360,
                brush_roundness=62,
                layer_id=str(layer_id),
                source_tool="ai_study_refinement",
                brush_engine_version=2,
                point_pressure=[0.72, 0.78, 0.84, 0.90, 0.96, 1.0, 0.96, 0.90, 0.84, 0.78, 0.70],
                point_tilt=[0.5] * 11,
                point_rotation=[0.5] * 11,
                point_load=[1.0 - index * 0.035 for index in range(11)],
                bristle_count=10,
                brush_seed=rng.randrange(1, 2**31 - 1),
                load_depletion=0.22,
            )
        )
    return strokes


def quality_report(runtime: dict[str, Any]) -> dict[str, Any]:
    comparison = dict(runtime.get("last_comparison") or {})
    reasons: list[str] = []
    if not comparison:
        reasons.append("render comparison has not run")
    if float(comparison.get("mean_absolute_error", 999.0)) > 32.0:
        reasons.append("mean reconstruction error is above 32")
    if float(comparison.get("luminance_correlation", 0.0)) < 0.86:
        reasons.append("luminance correlation is below 0.86")
    if float(comparison.get("structural_edge_f1", 0.0)) < 0.42:
        reasons.append("structural edge F1 is below 0.42")
    for focus in comparison.get("focus_regions") or []:
        if (
            float(focus.get("priority", 0.0)) >= 2.0
            and float(focus.get("mean_absolute_error", 999.0)) > 28.0
        ):
            reasons.append(f"focus region {focus.get('id')} error is above 28")
    if bool(runtime.get("baked_reference_pixels")):
        reasons.append("baked reference pixels are present")
    if int(runtime.get("stroke_count", 0)) < 1000:
        reasons.append("editable stroke count is below 1000")
    return {
        "schema": STUDY_SCHEMA,
        "session_id": runtime["session_id"],
        "status": "ready" if not reasons else "needs_refinement",
        "reasons": reasons,
        "stroke_count": int(runtime.get("stroke_count", 0)),
        "generated_layers": list(runtime.get("generated_layers") or []),
        "baked_reference_pixels": bool(runtime.get("baked_reference_pixels")),
        "comparison": comparison,
        "timings": list(runtime.get("timings") or []),
        "timings": list(runtime.get("timings") or []),
    }


def _cluster_regions(
    lab: np.ndarray,
    *,
    max_regions: int,
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    samples = lab.reshape((-1, 3)).astype(np.float32)
    count = max(3, min(24, int(max_regions or 12)))
    cv2.setRNGSeed(int(seed) & 0x7FFFFFFF)
    _, labels, centers = cv2.kmeans(
        samples,
        count,
        None,
        (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 24, 0.6),
        2,
        cv2.KMEANS_PP_CENTERS,
    )
    return labels.reshape(lab.shape[:2]), centers


def _quadratic_points(
    start: tuple[float, float],
    control: tuple[float, float],
    end: tuple[float, float],
    *,
    width: int,
    height: int,
) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for sample in range(11):
        t = sample / 10.0
        inv = 1.0 - t
        x = inv * inv * start[0] + 2.0 * inv * t * control[0] + t * t * end[0]
        y = inv * inv * start[1] + 2.0 * inv * t * control[1] + t * t * end[1]
        points.append(
            (
                max(0.0, min(1.0, x / max(1, width))),
                max(0.0, min(1.0, y / max(1, height))),
            )
        )
    return points


def _normalize_focus_regions(
    rows: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, row in enumerate(rows or []):
        if not isinstance(row, dict):
            continue
        bbox = list(row.get("bbox_norm") or [])
        if len(bbox) != 4:
            continue
        x0, y0, x1, y1 = [max(0.0, min(1.0, float(value))) for value in bbox]
        if x1 <= x0 or y1 <= y0:
            continue
        normalized.append(
            {
                "id": str(row.get("id") or f"focus-{index + 1}"),
                "bbox_norm": [x0, y0, x1, y1],
                "priority": max(0.1, min(3.0, float(row.get("priority", 1.0)))),
            }
        )
    return normalized


def _focus_weight(rows: list[dict[str, Any]], x: float, y: float) -> float:
    weight = 0.0
    for row in rows:
        x0, y0, x1, y1 = row["bbox_norm"]
        if x0 <= x <= x1 and y0 <= y <= y1:
            weight = max(weight, float(row.get("priority", 1.0)))
    return weight


__all__ = [
    "PHASE_PRESETS",
    "STUDY_SCHEMA",
    "analyze_reference",
    "compare_reference_to_render",
    "generate_phase_strokes",
    "generate_refinement_strokes",
    "quality_report",
    "segment_report",
]
