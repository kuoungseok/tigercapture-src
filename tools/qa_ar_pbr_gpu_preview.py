"""Headless QA for the AR/PBR GPU preview packet path."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DEFAULT_ASSET = ROOT / "debugCapture" / "ar_pbr_external_assets" / "es_fbx" / "es.fbx"
DEFAULT_OUT = ROOT / "debugCapture" / "ar_pbr_gpu_preview_qa.json"


def _fallback_scene_asset() -> Path:
    from app.ar_pbr.sample_scene import write_pbr_fbx_scene

    out = ROOT / "debugCapture" / "ar_pbr_scene_smoke" / "gpu_preview_qa_scene.fbx"
    out.parent.mkdir(parents=True, exist_ok=True)
    write_pbr_fbx_scene(out)
    return out


def _track_for_asset(asset: Path) -> dict[str, Any]:
    return {
        "id": "ar_pbr_gpu_preview_qa",
        "type": "ar_pbr_object",
        "asset_path": str(asset),
        "start_ms": 0,
        "end_ms": 1000,
        "transform": {
            "position": [0.0, 0.0, 0.0],
            "rotation": [0.0, 0.0, 0.0],
            "scale": [1.0, 1.0, 1.0],
        },
        "occlusion": True,
        "shadow_catcher": True,
        "reflection_catcher": True,
    }


def run_qa(asset: Path | None = None, *, width: int = 640, height: int = 360) -> dict[str, Any]:
    from app.ar_pbr.gpu_preview import build_gpu_preview_items
    from app.ar_pbr.importer import import_asset

    source = Path(asset or DEFAULT_ASSET)
    if not source.exists():
        source = _fallback_scene_asset()
    source = source.resolve()
    descriptor, import_diag = import_asset(
        source,
        settings={"placeholder_on_error": False, "max_triangles_per_geometry": 200_000},
    )
    track = _track_for_asset(source)
    camera = {
        "id": "qa_gpu_preview_camera",
        "frame_size": [int(width), int(height)],
        "intrinsics": {
            "fx": float(min(width, height)) * 1.15,
            "fy": float(min(width, height)) * 1.15,
            "cx": float(width) * 0.5,
            "cy": float(height) * 0.5,
        },
    }
    items, gpu_diag = build_gpu_preview_items(
        frame_size=(int(width), int(height)),
        time_ms=0,
        ar_tracks=[track],
        camera_solution=camera,
        settings={
            "asset_descriptors": {
                str(source): descriptor,
                str(track["asset_path"]): descriptor,
                track["id"]: descriptor,
            },
            "camera_z": 3.25,
            "gpu_triangle_limit": 40_000,
        },
    )
    triangle_count = sum(int(item.get("triangle_count", 0) or 0) for item in items)
    vertex_float_count = sum(len(item.get("vertices") or []) for item in items)
    shadow_triangle_count = sum(int(item.get("shadow_triangle_count", 0) or 0) for item in items)
    reflection_triangle_count = sum(int(item.get("reflection_triangle_count", 0) or 0) for item in items)
    shadow_vertex_float_count = sum(len(item.get("shadow_vertices") or []) for item in items)
    reflection_vertex_float_count = sum(len(item.get("reflection_vertices") or []) for item in items)
    ok = (
        bool(import_diag.get("ok", True))
        and bool(items)
        and triangle_count > 0
        and shadow_triangle_count > 0
        and reflection_triangle_count > 0
    )
    return {
        "ok": ok,
        "asset": str(source),
        "frame_size": [int(width), int(height)],
        "import": import_diag,
        "gpu_preview": gpu_diag,
        "summary": {
            "item_count": len(items),
            "triangle_count": triangle_count,
            "vertex_float_count": vertex_float_count,
            "shadow_triangle_count": shadow_triangle_count,
            "reflection_triangle_count": reflection_triangle_count,
            "shadow_vertex_float_count": shadow_vertex_float_count,
            "reflection_vertex_float_count": reflection_vertex_float_count,
            "uses_real_asset": source == DEFAULT_ASSET.resolve() if DEFAULT_ASSET.exists() else False,
            "fallback_scene": "gpu_preview_qa_scene.fbx" in source.name,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset", default=str(DEFAULT_ASSET))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=360)
    args = parser.parse_args()

    report = run_qa(Path(args.asset), width=max(16, args.width), height=max(16, args.height))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
