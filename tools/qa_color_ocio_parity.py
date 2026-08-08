"""Generate deterministic real-OCIO preview/export parity evidence."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.color_ocio import preferred_aces_ocio_uri
from app.color_runtime import apply_project_display_transform_rgb, ensure_display_lut


def _chart() -> np.ndarray:
    patches = np.asarray(
        [
            [242, 243, 243], [194, 195, 196], [145, 146, 146], [92, 93, 94],
            [45, 46, 47], [15, 15, 16], [193, 90, 99], [129, 162, 89],
            [88, 123, 164], [182, 145, 76], [92, 87, 151], [72, 138, 132],
            [224, 124, 47], [62, 91, 154], [197, 83, 80], [94, 58, 106],
            [159, 189, 63], [229, 161, 40], [0, 120, 191], [0, 142, 85],
            [238, 29, 35], [255, 242, 0], [193, 0, 103], [0, 0, 0],
        ],
        dtype=np.uint8,
    ).reshape(4, 6, 3)
    return np.repeat(np.repeat(patches, 80, axis=0), 80, axis=1)


def main() -> int:
    root = Path("debugCapture") / "color_ocio_parity"
    root.mkdir(parents=True, exist_ok=True)
    settings = {
        "input_space": "srgb",
        "working_space": "acescg",
        "view_transform": "aces-1.3",
        "output_space": "rec709",
        "output_transfer": "bt709",
        "ocio_config_path": preferred_aces_ocio_uri(),
    }
    source = _chart()
    preview, preview_report = apply_project_display_transform_rgb(source, settings)
    lut_path, lut_report = ensure_display_lut(settings, size=17)
    Image.fromarray(source, "RGB").save(root / "input_chart.png")
    Image.fromarray(preview, "RGB").save(root / "ocio_preview_chart.png")

    axis = np.linspace(0, 255, 17, dtype=np.uint8)
    samples = np.asarray(
        [[red, green, blue] for blue in axis for green in axis for red in axis],
        dtype=np.uint8,
    ).reshape(-1, 1, 3)
    expected, expected_report = apply_project_display_transform_rgb(samples, settings)
    values = [
        line
        for line in Path(lut_path).read_text(encoding="ascii").splitlines()
        if line and line[0].isdigit()
    ]
    actual = np.rint(
        np.asarray([[float(value) for value in line.split()] for line in values]) * 255.0
    ).clip(0, 255).astype(np.uint8)
    delta = np.abs(actual.astype(np.int16) - expected.reshape(-1, 3).astype(np.int16))
    report = {
        "schema": "tigerstudio.color.ocio_parity.v1",
        "ok": bool(
            preview_report.get("engine") == "ocio"
            and lut_report.get("engine") == "ocio"
            and expected_report.get("engine") == "ocio"
            and int(delta.max(initial=0)) == 0
        ),
        "ocio_config": settings["ocio_config_path"],
        "preview_engine": preview_report.get("engine"),
        "lut_engine": lut_report.get("engine"),
        "lut_size": 17,
        "grid_sample_count": int(actual.shape[0]),
        "max_abs_byte_delta": int(delta.max(initial=0)),
        "input_chart": str((root / "input_chart.png").resolve()),
        "preview_chart": str((root / "ocio_preview_chart.png").resolve()),
        "display_lut": str(Path(lut_path).resolve()),
    }
    (root / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
