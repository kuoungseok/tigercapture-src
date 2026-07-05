"""Render an AR/PBR FBX scene smoke image.

The default path generates a local ASCII FBX scene with PBR-like material
properties. Pass --asset to test a downloaded or user-provided FBX file.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from urllib.parse import urlparse
from urllib.request import urlretrieve

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
from PIL import Image

from app.ar_pbr.compositor import composite_preview_frame
from app.ar_pbr.importer import import_asset
from app.ar_pbr.sample_scene import write_pbr_fbx_scene


def _base_frame(width: int, height: int) -> np.ndarray:
    y = np.linspace(0, 1, height, dtype=np.float32)[:, None]
    x = np.linspace(0, 1, width, dtype=np.float32)[None, :]
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:, :, 0] = np.clip(22 + 40 * (1 - y), 0, 255).astype(np.uint8)
    frame[:, :, 1] = np.clip(28 + 55 * (1 - y), 0, 255).astype(np.uint8)
    frame[:, :, 2] = np.clip(34 + 65 * (1 - y) + 18 * x, 0, 255).astype(np.uint8)
    road_start = int(height * 0.58)
    frame[road_start:, :, :] = np.array([42, 43, 40], dtype=np.uint8)
    return frame


def _depth_frame(width: int, height: int) -> np.ndarray:
    y = np.linspace(0.25, 1.0, height, dtype=np.float32)[:, None]
    return np.repeat(y, width, axis=1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset", default="", help="Optional FBX asset path. Defaults to generated local scene.")
    parser.add_argument("--url", default="", help="Optional FBX URL to download into the smoke output folder.")
    parser.add_argument("--out", default=str(ROOT / "debugCapture" / "ar_pbr_scene_smoke" / "software_pbr_scene.png"))
    parser.add_argument("--width", type=int, default=512)
    parser.add_argument("--height", type=int, default=320)
    args = parser.parse_args()

    out_path = Path(args.out)
    if args.url:
        parsed = urlparse(args.url)
        filename = Path(parsed.path).name or "downloaded_scene.fbx"
        asset_path = out_path.parent / filename
        asset_path.parent.mkdir(parents=True, exist_ok=True)
        urlretrieve(args.url, asset_path)
    else:
        asset_path = Path(args.asset) if args.asset else out_path.with_suffix(".fbx")
    if not args.asset and not args.url:
        write_pbr_fbx_scene(asset_path)

    descriptor, import_diag = import_asset(asset_path)
    base = _base_frame(args.width, args.height)
    depth = _depth_frame(args.width, args.height)
    track = {
        "id": "scene_smoke",
        "type": "ar_pbr_object",
        "asset_path": str(asset_path),
        "start_ms": 0,
        "end_ms": 1000,
        "transform": {
            "position": [0.0, -0.08, 0.0],
            "rotation": [-18.0, 0.0, 0.0],
            "scale": [1.35, 1.35, 1.35],
        },
        "occlusion": True,
        "shadow_catcher": True,
        "reflection_catcher": True,
    }
    frame, render_diag = composite_preview_frame(
        base,
        time_ms=0,
        ar_tracks=[track],
        camera_solution={
            "id": "scene_smoke_cam",
            "frame_size": [args.width, args.height],
            "intrinsics": {
                "fx": float(args.width) * 0.92,
                "fy": float(args.width) * 0.92,
                "cx": float(args.width) * 0.5,
                "cy": float(args.height) * 0.54,
            },
        },
        depth_frame=depth,
        settings={
            "renderer": "software_pbr",
            "asset_descriptors": {str(asset_path): descriptor},
            "light_direction": [-0.35, -0.85, -0.4],
            "camera_z": 3.0,
            "shadow_blur": 4.0,
            "preserve_scene_layout": True,
        },
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(frame).save(out_path)
    diag_path = out_path.with_suffix(".json")
    diag_path.write_text(
        json.dumps({"import": import_diag, "render": render_diag}, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(json.dumps({
        "ok": True,
        "asset": str(asset_path),
        "image": str(out_path),
        "diagnostics": str(diag_path),
        "backend": render_diag.get("mode"),
        "rendered_track_count": render_diag.get("rendered_track_count"),
        "triangle_count": (render_diag.get("software_renderer") or {}).get("triangle_count"),
        "geometry_count": (render_diag.get("software_renderer") or {}).get("geometry_count"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
