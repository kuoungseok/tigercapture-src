"""Encode/decode a real ACES/HDR color chart and verify the delivery contract."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.color_management import probe_export_color_metadata
from app.color_ocio import preferred_aces_ocio_uri
from app.color_runtime import apply_project_display_transform_rgb
from app.subprocess_utils import hidden_subprocess_kwargs


PATCH_ROWS = 4
PATCH_COLUMNS = 6
PATCH_SIZE = 80


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
    ).reshape(PATCH_ROWS, PATCH_COLUMNS, 3)
    return np.repeat(
        np.repeat(patches, PATCH_SIZE, axis=0),
        PATCH_SIZE,
        axis=1,
    )


def _ffmpeg_path() -> str:
    from imageio_ffmpeg import get_ffmpeg_exe

    return str(get_ffmpeg_exe())


def _patch_centers(image: np.ndarray) -> np.ndarray:
    rows = []
    radius = 12
    for row in range(PATCH_ROWS):
        for column in range(PATCH_COLUMNS):
            cy = row * PATCH_SIZE + PATCH_SIZE // 2
            cx = column * PATCH_SIZE + PATCH_SIZE // 2
            sample = image[
                cy - radius:cy + radius,
                cx - radius:cx + radius,
            ].astype(np.float32)
            rows.append(sample.mean(axis=(0, 1)))
    return np.asarray(rows, dtype=np.float32)


def _srgb_patch_centers_to_lab(rgb: np.ndarray) -> np.ndarray:
    encoded = np.clip(np.asarray(rgb, dtype=np.float64) / 255.0, 0.0, 1.0)
    linear = np.where(
        encoded <= 0.04045,
        encoded / 12.92,
        ((encoded + 0.055) / 1.055) ** 2.4,
    )
    xyz = linear @ np.asarray(
        [
            [0.4124564, 0.3575761, 0.1804375],
            [0.2126729, 0.7151522, 0.0721750],
            [0.0193339, 0.1191920, 0.9503041],
        ],
        dtype=np.float64,
    ).T
    xyz /= np.asarray([0.95047, 1.0, 1.08883], dtype=np.float64)
    delta = 6.0 / 29.0
    f = np.where(
        xyz > delta ** 3,
        np.cbrt(xyz),
        xyz / (3.0 * delta * delta) + 4.0 / 29.0,
    )
    return np.stack(
        [
            116.0 * f[:, 1] - 16.0,
            500.0 * (f[:, 0] - f[:, 1]),
            200.0 * (f[:, 1] - f[:, 2]),
        ],
        axis=1,
    )


def run_encoded_color_qa(output_root: str | Path) -> dict[str, Any]:
    root = Path(output_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    ffmpeg = _ffmpeg_path()
    settings = {
        "input_space": "srgb",
        "input_transfer": "srgb",
        "working_space": "acescg",
        "output_space": "rec2020",
        "output_transfer": "pq",
        "view_transform": "aces-1.3",
        "hdr_mode": True,
        "ocio_config_path": preferred_aces_ocio_uri(),
    }
    source = _chart()
    preview, preview_report = apply_project_display_transform_rgb(source, settings)
    source_path = root / "input_chart.png"
    preview_path = root / "ocio_sdr_reference.png"
    output_path = root / "ocio_rec2020_pq_h265.mp4"
    decoded_path = root / "decoded_sdr_reference.png"
    Image.fromarray(source, "RGB").save(source_path)
    Image.fromarray(preview, "RGB").save(preview_path)

    height, width = preview.shape[:2]
    encode_command = [
        ffmpeg,
        "-hide_banner", "-loglevel", "error", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{width}x{height}", "-r", "24", "-i", "pipe:0",
        "-vf",
        "zscale=pin=bt709:tin=bt709:min=bt709:"
        "p=bt2020:t=smpte2084:m=bt2020nc,format=yuv420p10le",
        "-frames:v", "24",
        "-c:v", "libx265", "-preset", "medium", "-crf", "12",
        "-tag:v", "hvc1",
        "-colorspace", "bt2020nc",
        "-color_primaries", "bt2020",
        "-color_trc", "smpte2084",
        str(output_path),
    ]
    encoded_input = preview.tobytes() * 24
    encode = subprocess.run(
        encode_command,
        input=encoded_input,
        capture_output=True,
        timeout=120,
        **hidden_subprocess_kwargs(),
    )
    if encode.returncode != 0:
        raise RuntimeError(
            "HDR chart encode failed: "
            + encode.stderr.decode("utf-8", errors="replace")[-2000:]
        )

    decode_command = [
        ffmpeg,
        "-hide_banner", "-loglevel", "error",
        "-i", str(output_path),
        "-vf",
        "zscale=pin=bt2020:tin=smpte2084:min=bt2020nc:"
        "p=bt709:t=bt709:m=bt709,format=rgb24",
        "-frames:v", "1",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1",
    ]
    decode = subprocess.run(
        decode_command,
        capture_output=True,
        timeout=120,
        **hidden_subprocess_kwargs(),
    )
    expected_bytes = width * height * 3
    if decode.returncode != 0 or len(decode.stdout) < expected_bytes:
        raise RuntimeError(
            "HDR chart decode failed: "
            + decode.stderr.decode("utf-8", errors="replace")[-2000:]
        )
    decoded = np.frombuffer(
        decode.stdout[:expected_bytes],
        dtype=np.uint8,
    ).reshape(height, width, 3)
    Image.fromarray(decoded, "RGB").save(decoded_path)

    expected_centers = _patch_centers(preview)
    actual_centers = _patch_centers(decoded)
    delta = np.abs(expected_centers - actual_centers)
    delta_e76 = np.linalg.norm(
        _srgb_patch_centers_to_lab(expected_centers)
        - _srgb_patch_centers_to_lab(actual_centers),
        axis=1,
    )
    metadata = probe_export_color_metadata(
        output_path,
        {"color_management": settings},
    )
    mean_delta = float(delta.mean())
    max_delta = float(delta.max(initial=0.0))
    mean_delta_e76 = float(delta_e76.mean())
    max_delta_e76 = float(delta_e76.max(initial=0.0))
    ok = bool(
        preview_report.get("engine") == "ocio"
        and output_path.is_file()
        and output_path.stat().st_size > 1024
        and metadata.get("ok")
        and mean_delta <= 3.0
        and max_delta <= 18.0
        and mean_delta_e76 <= 1.5
        and max_delta_e76 <= 2.5
    )
    report = {
        "schema": "tigerstudio.color.encoded_export_qa.v1",
        "ok": ok,
        "ocio_config": settings["ocio_config_path"],
        "preview_engine": preview_report.get("engine"),
        "codec": "hevc",
        "pixel_format": "yuv420p10le",
        "frame_count": 24,
        "size": [width, height],
        "patch_count": PATCH_ROWS * PATCH_COLUMNS,
        "mean_abs_patch_byte_delta": mean_delta,
        "max_abs_patch_byte_delta": max_delta,
        "patch_byte_deltas": np.rint(delta).astype(int).tolist(),
        "mean_patch_delta_e76": mean_delta_e76,
        "max_patch_delta_e76": max_delta_e76,
        "patch_delta_e76": delta_e76.tolist(),
        "metadata": metadata,
        "artifacts": {
            "input_chart": str(source_path),
            "ocio_sdr_reference": str(preview_path),
            "hdr_video": str(output_path),
            "decoded_sdr_reference": str(decoded_path),
        },
    }
    (root / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    report = run_encoded_color_qa(
        ROOT / "debugCapture" / "color_encoded_export_qa"
    )
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
