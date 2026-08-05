"""Render a deterministic external-mesh DXR proof with the product bridge."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ar_pbr.native_rt import render_descriptor_native_rt


def _cube_descriptor() -> dict:
    vertices = [
        [-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1],
        [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1],
    ]
    triangles = [
        [0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7],
        [0, 1, 5], [0, 5, 4], [2, 3, 7], [2, 7, 6],
        [1, 2, 6], [1, 6, 5], [3, 0, 4], [3, 4, 7],
    ]
    return {"geometries": [{"vertices": vertices, "triangles": triangles}]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--hdri", type=Path)
    parser.add_argument("--mode", choices=("hybrid_rt", "path_traced"), default="hybrid_rt")
    parser.add_argument("--camera-visible", action="store_true")
    args = parser.parse_args()
    result = render_descriptor_native_rt(
        _cube_descriptor(),
        output_path=args.output,
        hdri_path=args.hdri,
        mode=args.mode,
        samples=16 if args.mode == "path_traced" else 1,
        bounces=3,
        camera_visible=args.camera_visible,
        reflection_visible=True,
        width=640,
        height=480,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
