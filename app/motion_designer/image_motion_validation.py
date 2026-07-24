"""Product validation for layered image assets and compiled Motion layers."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping


@dataclass(slots=True)
class ImageMotionValidationReport:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": bool(self.ok),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "metrics": dict(self.metrics),
        }


def _value(item: Any, name: str, default: Any = None) -> Any:
    if isinstance(item, Mapping):
        return item.get(name, default)
    return getattr(item, name, default)


def _fit_rgb_canvas(source: Path, width: int, height: int):
    import numpy as np
    from PIL import Image, ImageOps

    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
    scale = max(float(width) / max(1, image.width), float(height) / max(1, image.height))
    resized = image.resize(
        (
            max(1, int(round(image.width * scale))),
            max(1, int(round(image.height * scale))),
        ),
        Image.Resampling.LANCZOS,
    )
    left = max(0, (resized.width - width) // 2)
    top = max(0, (resized.height - height) // 2)
    return np.asarray(
        resized.crop((left, top, left + width, top + height)),
        dtype=np.uint8,
    )


def _alpha_composite(base, overlay):
    import numpy as np

    rgba = overlay.astype(np.float32) / 255.0
    alpha = rgba[:, :, 3:4]
    return np.clip(
        base.astype(np.float32) * (1.0 - alpha)
        + rgba[:, :, :3] * 255.0 * alpha,
        0,
        255,
    ).astype(np.uint8)


def _global_ssim(left, right, valid):
    import numpy as np

    x = left.astype(np.float64)[valid]
    y = right.astype(np.float64)[valid]
    if x.size == 0 or y.size == 0:
        return 1.0
    mu_x = float(x.mean())
    mu_y = float(y.mean())
    var_x = float(x.var())
    var_y = float(y.var())
    covariance = float(((x - mu_x) * (y - mu_y)).mean())
    c1 = 6.5025
    c2 = 58.5225
    denominator = (mu_x * mu_x + mu_y * mu_y + c1) * (var_x + var_y + c2)
    if denominator <= 0:
        return 1.0 if abs(mu_x - mu_y) <= 1e-6 else 0.0
    return max(
        -1.0,
        min(
            1.0,
            ((2 * mu_x * mu_y + c1) * (2 * covariance + c2)) / denominator,
        ),
    )


def reconstruction_metrics(result: Any) -> dict[str, Any]:
    import numpy as np
    from PIL import Image

    width = max(1, int(_value(result, "width", 1)))
    height = max(1, int(_value(result, "height", 1)))
    source_path = Path(str(_value(result, "source_path", "") or ""))
    background_path = Path(str(_value(result, "background_path", "") or ""))
    if not source_path.is_file() or not background_path.is_file():
        return {"available": False}

    source = _fit_rgb_canvas(source_path, width, height)
    with Image.open(background_path) as opened:
        background = np.asarray(
            opened.convert("RGBA").resize((width, height), Image.Resampling.LANCZOS),
            dtype=np.uint8,
        )
    composite = background[:, :, :3].copy()
    background_alpha = background[:, :, 3:4].astype(np.float32) / 255.0
    composite = np.clip(composite.astype(np.float32) * background_alpha, 0, 255).astype(np.uint8)

    elements = list(_value(result, "elements", []) or [])
    visual = [
        item for item in elements
        if str(_value(item, "role", "")) != "text"
        and str(_value(item, "rgba_path", "") or "")
    ]
    visual.sort(
        key=lambda item: int(
            dict(_value(item, "metadata", {}) or {}).get("z_order", 0) or 0
        )
    )
    for item in visual:
        path = Path(str(_value(item, "rgba_path", "") or ""))
        if not path.is_file():
            continue
        with Image.open(path) as opened:
            overlay = np.asarray(
                opened.convert("RGBA").resize((width, height), Image.Resampling.LANCZOS),
                dtype=np.uint8,
            )
        composite = _alpha_composite(composite, overlay)

    valid = np.ones((height, width), dtype=bool)
    for item in elements:
        if str(_value(item, "role", "")) != "text":
            continue
        x, y, box_width, box_height = [
            int(value) for value in list(_value(item, "bbox", (0, 0, 1, 1)))[:4]
        ]
        margin = max(2, int(round(box_height * 0.22)))
        valid[
            max(0, y - margin):min(height, y + box_height + margin),
            max(0, x - margin):min(width, x + box_width + margin),
        ] = False

    difference = np.abs(source.astype(np.int16) - composite.astype(np.int16))
    selected = difference[valid]
    mean_abs_error = float(selected.mean()) if selected.size else 0.0
    p95_abs_error = float(np.percentile(selected, 95.0)) if selected.size else 0.0
    return {
        "available": True,
        "mean_abs_error": mean_abs_error,
        "p95_abs_error": p95_abs_error,
        "global_ssim": _global_ssim(source, composite, valid),
        "valid_pixel_ratio": float(np.count_nonzero(valid)) / float(max(1, valid.size)),
    }


def validate_decomposition_result(result: Any) -> ImageMotionValidationReport:
    errors: list[str] = []
    warnings: list[str] = []
    elements = list(_value(result, "elements", []) or [])
    ids = [str(_value(item, "id", "") or "") for item in elements]
    if len(ids) != len(set(ids)):
        errors.append("Decomposition contains duplicate element ids.")
    if not ids:
        errors.append("Decomposition contains no editable elements.")
    background_path = Path(str(_value(result, "background_path", "") or ""))
    if not background_path.is_file():
        errors.append("Decomposition background asset is missing.")
    for item in elements:
        if str(_value(item, "role", "")) == "text":
            continue
        rgba_path = Path(str(_value(item, "rgba_path", "") or ""))
        mask_path = Path(str(_value(item, "mask_path", "") or ""))
        if not rgba_path.is_file():
            errors.append(f"RGBA asset is missing for {_value(item, 'id', '')}.")
        if not mask_path.is_file():
            errors.append(f"Mask asset is missing for {_value(item, 'id', '')}.")

    diagnostics = dict(_value(result, "diagnostics", {}) or {})
    graph = diagnostics.get("layer_graph")
    if isinstance(graph, Mapping):
        from .layer_graph import validate_layer_graph

        graph_warnings = validate_layer_graph(graph)
        errors.extend(
            item for item in graph_warnings
            if "cycle" in item.casefold() or "duplicate" in item.casefold()
        )
        warnings.extend(item for item in graph_warnings if item not in errors)
    metrics = reconstruction_metrics(result)
    if metrics.get("available"):
        if float(metrics.get("global_ssim", 0.0)) < 0.94:
            warnings.append("First-frame reconstruction similarity is below the automatic-approval target.")
        if float(metrics.get("mean_abs_error", 999.0)) > 8.0:
            warnings.append("First-frame reconstruction error is above the automatic-approval target.")
    else:
        warnings.append("First-frame reconstruction metrics are unavailable.")
    return ImageMotionValidationReport(
        ok=not errors,
        errors=list(dict.fromkeys(errors)),
        warnings=list(dict.fromkeys(warnings)),
        metrics=metrics,
    )


def _keyframe_signature(prop: Any) -> list[tuple[int, Any]]:
    return [
        (int(_value(item, "time_ms", 0)), _value(item, "value"))
        for item in list(_value(prop, "keyframes", []) or [])
    ]


def validate_compiled_image_layers(
    layers: Iterable[Any],
) -> ImageMotionValidationReport:
    rows = list(layers)
    errors: list[str] = []
    warnings: list[str] = []
    by_id = {str(_value(item, "id", "")): item for item in rows}
    background = next((
        item for item in rows
        if dict(_value(item, "metadata", {}) or {})
        .get("image_decomposition", {})
        .get("role") == "background"
    ), None)
    independent_signatures: list[tuple[Any, Any]] = []
    for layer in rows:
        parent_id = str(_value(layer, "parent_id", "") or "")
        if parent_id and parent_id not in by_id:
            errors.append(f"Compiled image layer has a missing parent: {parent_id}")
        metadata = dict(_value(layer, "metadata", {}) or {})
        decomposition = metadata.get("image_decomposition")
        if not isinstance(decomposition, Mapping):
            continue
        if bool(decomposition.get("motion_lock_to_background")) and background is not None:
            layer_transform = _value(layer, "transform")
            background_transform = _value(background, "transform")
            if (
                _keyframe_signature(_value(layer_transform, "position"))
                != _keyframe_signature(_value(background_transform, "position"))
                or _keyframe_signature(_value(layer_transform, "scale"))
                != _keyframe_signature(_value(background_transform, "scale"))
            ):
                errors.append(
                    f"Background-locked layer drifted from the camera group: {_value(layer, 'name', '')}"
                )
        choreography = metadata.get("motion_choreography")
        if isinstance(choreography, Mapping):
            if not choreography.get("lock_to_background") and not choreography.get("lock_to_parent"):
                independent_signatures.append((
                    tuple(choreography.get("end_offset_ratio") or ()),
                    int(choreography.get("start_ms", 0) or 0),
                ))
    if len(independent_signatures) > 1 and len(set(independent_signatures)) == 1:
        warnings.append("All independent image layers use the same motion signature.")
    return ImageMotionValidationReport(
        ok=not errors,
        errors=list(dict.fromkeys(errors)),
        warnings=list(dict.fromkeys(warnings)),
        metrics={"layer_count": len(rows)},
    )


__all__ = [
    "ImageMotionValidationReport",
    "reconstruction_metrics",
    "validate_compiled_image_layers",
    "validate_decomposition_result",
]
