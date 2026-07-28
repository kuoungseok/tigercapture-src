"""Integrated product gates for editable 2026 Motion trend templates."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
from PySide6.QtGui import QImage

from app.color_management import parse_ffmpeg_color_stream_text

from .export_pipeline import MotionExportCancelled, MotionProfileExporter
from .export_profiles import find_ffmpeg_executable, preflight_motion_export
from .export_renderer import MotionExportRenderer
from .precomposition import create_precomposition
from .recovery import read_motion_recovery, write_motion_recovery
from .schema import MotionComposition
from .templates import apply_template_to_composition


TREND_PRODUCT_GATE_SCHEMA = "tigerstudio.motion.trend_product_gate.v1"


def _same_document(left: MotionComposition, right: MotionComposition) -> bool:
    return json.dumps(
        left.to_dict(),
        sort_keys=True,
        separators=(",", ":"),
    ) == json.dumps(
        right.to_dict(),
        sort_keys=True,
        separators=(",", ":"),
    )


def _small_trend_composition(duration_ms: int) -> MotionComposition:
    base = MotionComposition(
        id="trend_product_gate",
        name="Trend Product Gate",
        width=320,
        height=180,
        fps=30,
        duration_ms=max(1000, int(duration_ms)),
    )
    result = apply_template_to_composition(
        base,
        "luxury_craft_product_reveal",
        variant="16:9",
        controls={
            "headline": "CRAFT IN MOTION",
            "subtitle": "A real editable product gate",
            "accent_color": "#62dfbe",
            "surface_color": "#0d1217",
            "cta": "MAKE THE NEXT FRAME",
            "duration_ms": max(1000, int(duration_ms)),
        },
    )
    result.id = base.id
    return result


def _small_glass_composition(duration_ms: int) -> MotionComposition:
    base = MotionComposition(
        id="trend_glass_hdr_gate",
        name="Trend Glass HDR Gate",
        width=320,
        height=180,
        fps=30,
        duration_ms=max(1000, int(duration_ms)),
    )
    result = apply_template_to_composition(
        base,
        "liquid_glass_app_promo",
        variant="16:9",
        controls={
            "headline": "GLASS IN MOTION",
            "subtitle": "Color-managed backdrop refraction",
            "accent_color": "#dce85a",
            "surface_color": "#0d1217",
            "cta": "SHIP THE FRAME",
            "duration_ms": max(1000, int(duration_ms)),
        },
    )
    result.id = base.id
    return result


def run_trend_product_gate(
    output_root: str | Path,
    *,
    duration_ms: int = 60000,
    sequence_fps: float = 2.0,
    cancel_after_frames: int = 8,
) -> dict[str, Any]:
    root = Path(output_root).expanduser().resolve(strict=False)
    root.mkdir(parents=True, exist_ok=True)
    composition = _small_trend_composition(duration_ms)
    sequence_dir = root / "png_sequence"
    cancel_calls = 0

    def cancel_check() -> bool:
        nonlocal cancel_calls
        cancel_calls += 1
        return cancel_calls > max(1, int(cancel_after_frames))

    cancelled = False
    try:
        MotionProfileExporter(cancel_check=cancel_check).export(
            composition,
            "png_sequence",
            sequence_dir,
            fps=sequence_fps,
        )
    except MotionExportCancelled:
        cancelled = True
    partial = sorted(sequence_dir.glob("frame_*.png"))
    valid_partial_count = len(partial)
    corrupt_path = partial[0] if partial else None
    if corrupt_path is not None:
        corrupt_path.write_bytes(b"corrupt")
    resumed = MotionProfileExporter().export(
        composition,
        "png_sequence",
        sequence_dir,
        fps=sequence_fps,
        resume=True,
    )

    recovery_path = root / "trend.motion-recovery.json"
    write_motion_recovery(composition, recovery_path)
    recovered, recovery_report = read_motion_recovery(
        recovery_path,
        expected_composition_id=composition.id,
    )
    recovery_roundtrip = _same_document(recovered, composition)

    alpha_composition = MotionComposition.from_dict(composition.to_dict())
    alpha_composition.layers = [
        layer for layer in alpha_composition.layers
        if layer.metadata.get("template_role") != "background"
    ]
    alpha_path = root / "alpha.png"
    MotionProfileExporter().export(
        alpha_composition,
        "png_still",
        alpha_path,
        time_ms=min(500.0, alpha_composition.duration_ms * 0.1),
    )
    alpha_image = QImage(str(alpha_path)).convertToFormat(QImage.Format_RGBA8888)
    alpha_values = np.frombuffer(
        alpha_image.constBits(),
        dtype=np.uint8,
    ).reshape(alpha_image.height(), alpha_image.bytesPerLine())[
        :, : alpha_image.width() * 4
    ].reshape(alpha_image.height(), alpha_image.width(), 4)[..., 3]

    nested = MotionComposition.from_dict(composition.to_dict())
    first_scene = next(
        layer for layer in nested.layers
        if layer.metadata.get("template_role") == "scene"
    )
    child_ids = [
        layer.id for layer in nested.layers
        if layer.parent_id == first_scene.id
    ]
    nested_renderer = MotionExportRenderer(cache_capacity=2)
    nested_time = min(500.0, nested.duration_ms / 12.0)
    flat_frame = nested_renderer.render_rgba_array(nested, nested_time)
    create_precomposition(nested, child_ids, name="Trend Scene Content")
    nested_frame = nested_renderer.render_rgba_array(nested, nested_time)

    hdr = MotionComposition.from_dict(composition.to_dict())
    hdr.metadata["color_management"]["project"].update({
        "output_space": "rec2020",
        "output_transfer": "pq",
        "view_transform": "hdr-pq",
        "hdr_mode": True,
    })
    hdr_report = preflight_motion_export(
        hdr,
        "h265_mp4",
        output_path=root / "hdr.mp4",
        fps=sequence_fps,
    )
    hdr_artifact = _small_glass_composition(1000)
    hdr_artifact.metadata["color_management"]["project"].update({
        "output_space": "rec2020",
        "output_transfer": "pq",
        "view_transform": "hdr-pq",
        "hdr_mode": True,
    })
    hdr_artifact.metadata["tiled_export"] = {
        "contract": "tigerstudio.motion.tiled_export.v1",
        "enabled": True,
        "tile_size": 96,
    }
    hdr_artifact.revision += 1
    hdr_path = root / "trend_hdr.mp4"
    hdr_renderer = MotionExportRenderer(cache_capacity=2)
    hdr_result = MotionProfileExporter(hdr_renderer).export(
        hdr_artifact,
        "h265_mp4",
        hdr_path,
        fps=sequence_fps,
    )
    tiled_report = dict(hdr_renderer.last_tiled_report)
    hdr_probe = subprocess.run(
        [find_ffmpeg_executable(), "-hide_banner", "-i", str(hdr_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    hdr_stream = parse_ffmpeg_color_stream_text(hdr_probe.stderr)
    glass_effect_count = sum(
        effect.kind == "tiger_glass"
        for layer in hdr_artifact.layers
        for effect in layer.effects
    )
    glass_renderer = MotionExportRenderer(cache_capacity=2)
    glass_frame = glass_renderer.render_rgba_array(hdr_artifact, 500.0)
    full_glass = MotionComposition.from_dict(hdr_artifact.to_dict())
    full_glass.metadata.pop("tiled_export", None)
    full_glass.revision += 1
    full_glass_frame = glass_renderer.render_rgba_array(full_glass, 500.0)
    tiled_pixel_difference = np.abs(
        glass_frame.astype(np.int16) - full_glass_frame.astype(np.int16)
    )
    no_glass = MotionComposition.from_dict(full_glass.to_dict())
    for layer in no_glass.layers:
        layer.effects = [
            effect for effect in layer.effects
            if effect.kind != "tiger_glass"
        ]
    no_glass.revision += 1
    no_glass_frame = glass_renderer.render_rgba_array(no_glass, 500.0)
    glass_pixel_difference = np.abs(
        glass_frame.astype(np.int16) - no_glass_frame.astype(np.int16)
    )
    glass_changed_pixel_count = int(
        np.count_nonzero(np.any(glass_pixel_difference[..., :3] > 0, axis=2))
    )
    mp4_composition = _small_trend_composition(1000)
    mp4_path = root / "trend_preview.mp4"
    mp4_result = MotionProfileExporter().export(
        mp4_composition,
        "h264_mp4",
        mp4_path,
        fps=sequence_fps,
    )

    expected_frames = int(resumed["preflight"]["frame_count"]) if "preflight" in resumed else int(
        round(composition.duration_ms / 1000.0 * sequence_fps)
    )
    report = {
        "schema": TREND_PRODUCT_GATE_SCHEMA,
        "ok": bool(
            cancelled
            and valid_partial_count == max(1, int(cancel_after_frames))
            and resumed["sequence_complete"]
            and int(resumed["frame_count"]) == expected_frames
            and int(resumed["rendered_frame_count"]) > 0
            and recovery_roundtrip
            and recovery_report["ok"]
            and int(alpha_values.min()) == 0
            and int(alpha_values.max()) > 0
            and np.array_equal(flat_frame, nested_frame)
            and hdr_report["ok"]
            and hdr_path.is_file()
            and hdr_path.stat().st_size > 0
            and hdr_stream.get("color_primaries") == "bt2020"
            and hdr_stream.get("color_transfer") == "smpte2084"
            and glass_effect_count == 3
            and glass_changed_pixel_count > 0
            and int(tiled_report.get("tile_count", 0)) > 1
            and bool(tiled_report.get("full_frame_intermediate_avoided", False))
            and float(tiled_pixel_difference.mean()) < 0.5
            and mp4_path.is_file()
            and mp4_path.stat().st_size > 0
        ),
        "duration_ms": composition.duration_ms,
        "sequence_fps": float(sequence_fps),
        "cancelled": cancelled,
        "partial_frame_count": valid_partial_count,
        "corrupt_frame_repaired": bool(
            corrupt_path is not None
            and MotionProfileExporter._is_valid_png(corrupt_path)
        ),
        "resume": {
            "frame_count": int(resumed["frame_count"]),
            "rendered_frame_count": int(resumed["rendered_frame_count"]),
            "resumed_frame_count": int(resumed["resumed_frame_count"]),
            "sequence_complete": bool(resumed["sequence_complete"]),
            "manifest_path": str(resumed["manifest_path"]),
        },
        "recovery_roundtrip": recovery_roundtrip,
        "alpha": {
            "path": str(alpha_path),
            "minimum": int(alpha_values.min()),
            "maximum": int(alpha_values.max()),
            "storage": "straight",
            "composite": "premultiplied",
        },
        "nested_preview_export_parity": bool(np.array_equal(flat_frame, nested_frame)),
        "hdr_h265_preflight": {
            "ok": bool(hdr_report["ok"]),
            "errors": list(hdr_report["errors"]),
            "warnings": list(hdr_report["warnings"]),
        },
        "hdr_h265_artifact": {
            "path": str(hdr_path),
            "frame_count": int(hdr_result["frame_count"]),
            "bytes": hdr_path.stat().st_size if hdr_path.is_file() else 0,
            "color_primaries": str(hdr_stream.get("color_primaries") or ""),
            "color_transfer": str(hdr_stream.get("color_transfer") or ""),
            "glass_effect_count": int(glass_effect_count),
            "glass_changed_pixel_count": int(glass_changed_pixel_count),
            "glass_mean_rgb_abs_difference": float(
                glass_pixel_difference[..., :3].mean()
            ),
            "tiled_export": tiled_report,
            "tiled_full_mean_abs_difference": float(
                tiled_pixel_difference.mean()
            ),
            "tiled_full_max_abs_difference": int(
                tiled_pixel_difference.max()
            ),
        },
        "mp4": {
            "path": str(mp4_path),
            "frame_count": int(mp4_result["frame_count"]),
            "bytes": mp4_path.stat().st_size if mp4_path.is_file() else 0,
        },
    }
    return report


__all__ = [
    "TREND_PRODUCT_GATE_SCHEMA",
    "run_trend_product_gate",
]
