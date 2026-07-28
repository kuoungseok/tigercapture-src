"""Headless source/frozen smoke probe for the shared color runtime."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np


def build_color_runtime_probe_report() -> dict[str, Any]:
    from app.color_ocio import (
        build_ocio_plan,
        list_builtin_ocio_configs,
        preferred_aces_ocio_uri,
    )
    from app.color_runtime import (
        apply_project_display_transform_rgb,
        ensure_display_lut,
    )

    config_uri = preferred_aces_ocio_uri()
    settings = {
        "input_space": "srgb",
        "input_transfer": "srgb",
        "working_space": "acescg",
        "output_space": "rec709",
        "output_transfer": "bt709",
        "view_transform": "aces-1.3",
        "ocio_config_path": config_uri,
    }
    source = np.asarray(
        [[[51, 102, 204], [255, 128, 26], [128, 128, 128]]],
        dtype=np.uint8,
    )
    transformed, transform_report = apply_project_display_transform_rgb(
        source,
        settings,
    )
    lut_path, lut_report = ensure_display_lut(settings, size=5)
    plan = build_ocio_plan(
        settings,
        source="srgb",
        destination="rec709",
    )
    try:
        import PyOpenColorIO as ocio

        ocio_version = str(ocio.__version__)
    except Exception:
        ocio_version = ""
    ok = bool(
        ocio_version
        and config_uri
        and plan.enabled
        and transform_report.get("engine") == "ocio"
        and transform_report.get("applied")
        and Path(lut_path).is_file()
        and lut_report.get("engine") == "ocio"
        and not np.array_equal(source, transformed)
    )
    return {
        "schema": "tigerstudio.color.frozen_runtime_probe.v1",
        "ok": ok,
        "frozen": bool(getattr(sys, "frozen", False)),
        "executable": str(Path(sys.executable).resolve()),
        "ocio_version": ocio_version,
        "builtin_config_count": len(list_builtin_ocio_configs()),
        "config_uri": config_uri,
        "plan": plan.to_dict(),
        "source_pixels": source.tolist(),
        "output_pixels": transformed.tolist(),
        "transform": transform_report,
        "lut": {
            "path": str(Path(lut_path).resolve()) if lut_path else "",
            "exists": bool(lut_path and Path(lut_path).is_file()),
            "report": lut_report,
        },
    }


def write_color_runtime_probe_report(path: str | Path) -> dict[str, Any]:
    output = Path(path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    report = build_color_runtime_probe_report()
    output.write_text(
        json.dumps(report, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return report


__all__ = [
    "build_color_runtime_probe_report",
    "write_color_runtime_probe_report",
]
