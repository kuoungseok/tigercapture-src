from __future__ import annotations

import argparse
import gc
import json
import sys
import time
import tracemalloc
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OFFICIAL_SOURCES = {
    "json_schema_array_length": (
        "https://json-schema.org/understanding-json-schema/reference/array#length"
    ),
    "qt_qcolor_rgb_hsv": "https://doc.qt.io/qt-6/qcolor.html",
    "adobe_alpha_channel_options": (
        "https://helpx.adobe.com/photoshop/using/"
        "saving-selections-alpha-channel-masks.html#edit_channel_options"
    ),
}


def _square_source(size: int) -> Image.Image:
    axis = np.arange(size, dtype=np.uint16)
    red = np.broadcast_to((axis % 256).astype(np.uint8), (size, size))
    green = red.T.copy()
    blue = ((red.astype(np.uint16) + green.astype(np.uint16)) // 2).astype(
        np.uint8
    )
    return Image.fromarray(np.dstack((red, green, blue)), "RGB")


def _array_metrics(generated: dict[str, Any]) -> dict[str, Any]:
    arrays = [value for value in generated["maps"].values() if isinstance(value, np.ndarray)]
    unique_arrays = {id(value): value for value in arrays}
    return {
        "map_array_references": len(arrays),
        "unique_array_count": len(unique_arrays),
        "referenced_array_bytes": sum(value.nbytes for value in arrays),
        "unique_retained_array_bytes": sum(value.nbytes for value in unique_arrays.values()),
        "maps": {
            name: {
                "shape": list(value.shape),
                "dtype": str(value.dtype),
                "nbytes": int(value.nbytes),
            }
            for name, value in generated["maps"].items()
            if isinstance(value, np.ndarray)
        },
    }


def _measure_cpu_generation(size: int) -> dict[str, Any]:
    from app.ar_pbr.texture_map_lab import generate_texture_maps_from_image

    source = _square_source(size)
    gc.collect()
    tracemalloc.start()
    started = time.perf_counter()
    generated = generate_texture_maps_from_image(
        source,
        max_size=size,
        backend="cpu",
        allow_cpu=True,
        source_path="measurement://m54-gradient",
    )
    elapsed_seconds = time.perf_counter() - started
    current_bytes, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    arrays = _array_metrics(generated)
    retained = arrays["unique_retained_array_bytes"]
    return {
        "width": size,
        "height": size,
        "backend": generated["backend"]["active"],
        "generated_size": generated["size"],
        "elapsed_seconds_observed_not_a_gate": elapsed_seconds,
        "tracemalloc_current_bytes": current_bytes,
        "tracemalloc_peak_bytes_observed_not_a_gate": peak_bytes,
        "unique_retained_bytes_per_pixel": retained / (size * size),
        **arrays,
    }


def run_measurement() -> dict[str, Any]:
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog
    from app.painter_action_contract import (
        PAINT_ACTION_PBR_PREVIEW_DEFAULT_PX,
        PAINT_ACTION_PBR_PREVIEW_MAX_PX,
        PAINT_ACTION_PBR_PREVIEW_MIN_PX,
        PAINT_ACTION_PBR_PREVIEW_RESOURCE_CONTRACT,
        PAINT_ACTION_PBR_RETAINED_ARRAY_BUDGET_BYTES,
        normalize_painter_pbr_preview_width,
    )
    from app.painter_saved_selection_channels import (
        normalize_saved_selection_channel_overlay_opacity,
    )

    registry = ActionRegistry(owner=None)
    color_schema = registry.get_action_schema("paint.color.numeric.set")[
        "params_schema"
    ]["properties"]["values"]
    overlay_schema = registry.get_action_schema(
        "paint.selection.channel.options.set"
    )["params_schema"]["properties"]["overlay_opacity_percent"]
    preview_schema = registry.get_action_schema("paint.pbr.preview")[
        "params_schema"
    ]["properties"]["width"]

    class _ColorTarget:
        def __init__(self) -> None:
            self.applied = None

        def _apply_pen_color(self, color, *, remember: bool) -> None:
            self.applied = (color, remember)

        def _refresh_toolbar_color_swatches(self) -> None:
            return None

    color_target = _ColorTarget()
    valid_color = PaintDialog._set_painter_numeric_color(
        color_target, "rgb", [12, 34, 56]
    )
    invalid_color_inputs = (
        [1, 2],
        [1, 2, 3, 4],
        [True, 2, 3],
        ["1", 2, 3],
        [float("nan"), 2, 3],
        [float("inf"), 2, 3],
    )
    invalid_color_blocked = []
    for values in invalid_color_inputs:
        try:
            PaintDialog._set_painter_numeric_color(color_target, "rgb", values)
        except (TypeError, ValueError):
            invalid_color_blocked.append(True)
        else:
            invalid_color_blocked.append(False)

    opacity_endpoints = [
        normalize_saved_selection_channel_overlay_opacity(value)
        for value in (0, 100)
    ]
    invalid_opacity_blocked = []
    for value in (True, -1, 101, 50.0, "50", None):
        try:
            normalize_saved_selection_channel_overlay_opacity(value)
        except (TypeError, ValueError):
            invalid_opacity_blocked.append(True)
        else:
            invalid_opacity_blocked.append(False)

    normalized_widths = [
        normalize_painter_pbr_preview_width(value)
        for value in (
            PAINT_ACTION_PBR_PREVIEW_MIN_PX,
            PAINT_ACTION_PBR_PREVIEW_DEFAULT_PX,
            PAINT_ACTION_PBR_PREVIEW_MAX_PX,
        )
    ]
    invalid_width_blocked = []
    for value in (
        True,
        64.0,
        "64",
        None,
        PAINT_ACTION_PBR_PREVIEW_MIN_PX - 1,
        PAINT_ACTION_PBR_PREVIEW_MAX_PX + 1,
    ):
        try:
            normalize_painter_pbr_preview_width(value)
        except (TypeError, ValueError):
            invalid_width_blocked.append(True)
        else:
            invalid_width_blocked.append(False)

    cpu_measurements = [
        _measure_cpu_generation(size) for size in (64, 256, 512, 1024)
    ]
    retained_bpp_values = [
        row["unique_retained_bytes_per_pixel"] for row in cpu_measurements
    ]
    measured_bpp = cpu_measurements[-1]["unique_retained_bytes_per_pixel"]
    projected_2048_bytes = int(measured_bpp * 2048 * 2048)
    projected_old_8192_bytes = int(measured_bpp * 8192 * 8192)
    checks = {
        "numeric_color_schema_requires_exactly_three_components": (
            color_schema.get("type") == "array"
            and color_schema.get("items") == {"type": "number"}
            and color_schema.get("minItems") == 3
            and color_schema.get("maxItems") == 3
        ),
        "numeric_color_implementation_accepts_three_components": (
            valid_color["rgb"] == [12, 34, 56]
        ),
        "numeric_color_rejects_wrong_length_bool_and_nonfinite": all(
            invalid_color_blocked
        ),
        "overlay_schema_is_integer_zero_through_one_hundred": overlay_schema
        == {"type": "integer", "minimum": 0, "maximum": 100},
        "overlay_normalizer_accepts_both_endpoints": opacity_endpoints == [0, 100],
        "overlay_normalizer_rejects_coercion_and_out_of_range": all(
            invalid_opacity_blocked
        ),
        "pbr_preview_schema_matches_runtime_policy": preview_schema
        == {
            "type": "integer",
            "minimum": PAINT_ACTION_PBR_PREVIEW_MIN_PX,
            "maximum": PAINT_ACTION_PBR_PREVIEW_MAX_PX,
        },
        "pbr_preview_normalizer_accepts_min_default_max": normalized_widths
        == [64, 512, 1024],
        "pbr_preview_normalizer_rejects_coercion_and_out_of_range": all(
            invalid_width_blocked
        ),
        "cpu_measurements_generated_requested_square_sizes": all(
            row["backend"] == "cpu"
            and row["generated_size"] == [row["width"], row["height"]]
            for row in cpu_measurements
        ),
        "retained_array_bytes_scale_exactly_per_pixel": len(
            {round(value, 8) for value in retained_bpp_values}
        )
        == 1,
        "maximum_preview_retained_arrays_fit_authored_budget": (
            cpu_measurements[-1]["unique_retained_array_bytes"]
            <= PAINT_ACTION_PBR_RETAINED_ARRAY_BUDGET_BYTES
        ),
        "next_power_of_two_exceeds_authored_retained_array_budget": (
            projected_2048_bytes > PAINT_ACTION_PBR_RETAINED_ARRAY_BUDGET_BYTES
        ),
        "old_8192_cap_would_exceed_authored_budget": (
            projected_old_8192_bytes > PAINT_ACTION_PBR_RETAINED_ARRAY_BUDGET_BYTES
            and PAINT_ACTION_PBR_PREVIEW_MAX_PX < 8192
        ),
        "resource_contract_rejects_universal_and_quality_claims": (
            PAINT_ACTION_PBR_PREVIEW_RESOURCE_CONTRACT[
                "universal_latency_or_memory_safety_claim"
            ]
            is False
            and PAINT_ACTION_PBR_PREVIEW_RESOURCE_CONTRACT["gpu_parity_claim"]
            is False
            and PAINT_ACTION_PBR_PREVIEW_RESOURCE_CONTRACT[
                "visual_quality_threshold_claim"
            ]
            is False
        ),
    }
    return {
        "schema": "tigerstudio.painter.action_schema_resource_measurement.v1",
        "scope": "painting_only_ui_design_excluded",
        "official_sources": OFFICIAL_SOURCES,
        "authored_policy": dict(PAINT_ACTION_PBR_PREVIEW_RESOURCE_CONTRACT),
        "claim_boundary": {
            "universal_latency_or_memory_safety_claim": False,
            "gpu_parity_claim": False,
            "visual_quality_threshold_claim": False,
            "external_product_behavior_equivalence_claim": False,
            "validated_claim": (
                "action_schema_runtime_alignment_and_measured_cpu_retained_arrays"
            ),
        },
        "measurements": {
            "cpu_generation": cpu_measurements,
            "measured_unique_retained_bytes_per_pixel": measured_bpp,
            "authored_retained_array_budget_bytes": (
                PAINT_ACTION_PBR_RETAINED_ARRAY_BUDGET_BYTES
            ),
            "projected_2048_unique_retained_array_bytes": projected_2048_bytes,
            "projected_old_8192_unique_retained_array_bytes": (
                projected_old_8192_bytes
            ),
        },
        "checks": checks,
        "checks_passed": sum(bool(value) for value in checks.values()),
        "checks_total": len(checks),
        "passed": all(bool(value) for value in checks.values()),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default=str(
            ROOT
            / "debugCapture"
            / "painter"
            / "evidence_audit"
            / "m54_action_schema_resources.json"
        ),
    )
    args = parser.parse_args(argv)
    report = run_measurement()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "path": str(output.resolve()),
                "passed": report["passed"],
                "checks_passed": report["checks_passed"],
                "checks_total": report["checks_total"],
            }
        )
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
