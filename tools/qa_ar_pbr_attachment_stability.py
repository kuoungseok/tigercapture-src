"""Headless QA for AR/PBR video attachment stability.

This checks the product contract that a 3D object can stay attached to a video
frame point through the GPU preview packet path. It does not try to grade final
PBR quality; it catches coordinate, placement, occlusion, and catcher regressions
that make an object feel detached from the footage.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_OUT = ROOT / "debugCapture" / "ar_pbr_attachment_stability_qa.json"


def _descriptor() -> dict[str, Any]:
    return {
        "geometries": [
            {
                "name": "qa_attachment_card",
                "vertices": [
                    [-1.0, -1.0, 0.0],
                    [1.0, -1.0, 0.0],
                    [1.0, 1.0, 0.0],
                    [-1.0, 1.0, 0.0],
                ],
                "triangles": [[0, 1, 2], [0, 2, 3]],
                "bounds": {"center": [0.0, 0.0, 0.0], "size": [2.0, 2.0, 0.2]},
            }
        ],
        "materials": [{"base_color": [0.98, 0.36, 0.16, 1.0], "roughness": 0.38}],
    }


def _camera(width: int, height: int) -> dict[str, Any]:
    focal = float(min(width, height))
    return {
        "id": "qa_ar_pbr_attachment_camera",
        "frame_size": [int(width), int(height)],
        "intrinsics": {
            "fx": focal,
            "fy": focal,
            "cx": float(width) * 0.5,
            "cy": float(height) * 0.5,
        },
        "plane": {
            "point": [0.0, 0.0, 3.0],
            "normal": [0.0, 0.0, 1.0],
            "d": -3.0,
        },
    }


def _track(image_point: tuple[float, float], *, occlusion: bool = True) -> dict[str, Any]:
    return {
        "id": "qa_ar_pbr_attachment",
        "type": "ar_pbr_object",
        "asset_path": "qa_attachment_card.fbx",
        "start_ms": 0,
        "end_ms": 3000,
        "transform": {
            "position": [0.0, 0.0, 0.0],
            "rotation": [0.0, 0.0, 0.0],
            "scale": [0.72, 0.72, 0.72],
        },
        "placement": {
            "mode": "road_plane_anchor",
            "coordinate_space": "normalized",
            "image_point": [float(image_point[0]), float(image_point[1])],
        },
        "occlusion": bool(occlusion),
        "shadow_catcher": True,
        "reflection_catcher": True,
        "render": {
            "lighting": {
                "direct_strength": 0.85,
                "ibl_exposure": 1.1,
                "shadow_strength": 0.62,
            },
        },
    }


def _item_center_px(item: dict[str, Any], width: int, height: int) -> tuple[float, float] | None:
    vertices = item.get("vertices")
    if not isinstance(vertices, list) or len(vertices) < 6:
        return None
    xs = [float(value) for value in vertices[0::6]]
    ys = [float(value) for value in vertices[1::6]]
    if not xs or not ys:
        return None
    ndc_x = sum(xs) / len(xs)
    ndc_y = sum(ys) / len(ys)
    return ((ndc_x + 1.0) * 0.5 * width, (1.0 - ndc_y) * 0.5 * height)


def _draw_tracking_patch(frame: np.ndarray, *, center: tuple[int, int], scale: float = 1.0, rotation_deg: float = 0.0) -> bool:
    try:
        import cv2
    except Exception:
        return False
    patch = np.zeros((24, 24, 3), dtype=np.uint8)
    patch[4:20, 5:9] = [245, 245, 245]
    patch[15:19, 5:20] = [210, 210, 210]
    patch[5:11, 14:20] = [150, 150, 150]
    size = max(8, int(round(24 * float(scale))))
    patch = cv2.resize(patch, (size, size), interpolation=cv2.INTER_LINEAR)
    if abs(float(rotation_deg)) > 1e-6:
        matrix = cv2.getRotationMatrix2D((size * 0.5, size * 0.5), float(rotation_deg), 1.0)
        patch = cv2.warpAffine(patch, matrix, (size, size), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0))
    cx, cy = int(center[0]), int(center[1])
    x0 = max(0, cx - size // 2)
    y0 = max(0, cy - size // 2)
    x1 = min(frame.shape[1], x0 + size)
    y1 = min(frame.shape[0], y0 + size)
    frame[y0:y1, x0:x1] = np.maximum(frame[y0:y1, x0:x1], patch[: y1 - y0, : x1 - x0])
    return True


def _tracking_transform_probe() -> dict[str, Any]:
    from app.ar_pbr.schema import normalize_ar_track
    from app.ar_pbr.scene_anchor import promote_track_to_scene_anchor, update_scene_anchor_for_frame

    width, height = 160, 120
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:, :, 1] = 35
    if not _draw_tracking_patch(frame, center=(68, 76), scale=1.0, rotation_deg=0.0):
        return {"ok": False, "reason": "opencv unavailable for affine tracking probe"}
    track = normalize_ar_track({
        "id": "qa_affine_tracking",
        "type": "ar_pbr_object",
        "asset_path": "qa_attachment_card.fbx",
        "placement": {
            "mode": "manual",
            "image_point": [68 / width, 76 / height],
            "coordinate_space": "normalized",
        },
        "transform": {
            "position": [0.0, -0.72, 0.0],
            "rotation": [0.0, 8.0, 3.0],
            "scale": [1.2, 1.2, 1.2],
        },
    })
    anchored, promote_diag = promote_track_to_scene_anchor(
        track,
        frame,
        time_ms=0,
        source_id="qa_affine_tracking",
        store_caches=False,
    )
    shifted = np.zeros_like(frame)
    shifted[:, :, 1] = 35
    _draw_tracking_patch(shifted, center=(87, 76), scale=1.22, rotation_deg=18.0)
    updated, depth, solution, runtime_diag = update_scene_anchor_for_frame(
        anchored,
        shifted,
        time_ms=33,
        source_id="qa_affine_tracking",
    )
    tracking = runtime_diag.get("tracking", {}) if isinstance(runtime_diag, dict) else {}
    scale_ratio = float(tracking.get("scale", 1.0) or 1.0) if isinstance(tracking, dict) else 1.0
    rotation_delta = float(tracking.get("rotation_deg", 0.0) or 0.0) if isinstance(tracking, dict) else 0.0
    multi_probe = tracking.get("multi_probe", {}) if isinstance(tracking, dict) else {}
    multi_probe_ok = (
        isinstance(multi_probe, dict)
        and bool(multi_probe.get("ok"))
        and int(multi_probe.get("matched_probe_count", 0) or 0) >= 3
    )
    scale_changed = updated["transform"]["scale"][0] > anchored["transform"]["scale"][0] * 1.05
    rotation_changed = abs(updated["transform"]["rotation"][2] - anchored["transform"]["rotation"][2]) >= 9.0
    moved = updated["placement"]["image_point"][0] > anchored["placement"]["image_point"][0] + 0.07
    ok = (
        bool(promote_diag.get("ok"))
        and bool(runtime_diag.get("ok"))
        and depth is not None
        and solution is not None
        and moved
        and multi_probe_ok
        and scale_ratio > 1.05
        and abs(rotation_delta) >= 9.0
        and scale_changed
        and rotation_changed
    )
    return {
        "ok": ok,
        "moved": moved,
        "multi_probe_ok": multi_probe_ok,
        "scale_ratio": round(scale_ratio, 3),
        "rotation_delta_deg": round(rotation_delta, 3),
        "scale_changed": scale_changed,
        "rotation_changed": rotation_changed,
        "promote": promote_diag,
        "runtime": runtime_diag,
        "updated_transform": updated.get("transform"),
    }


def run_qa(*, width: int = 320, height: int = 180) -> dict[str, Any]:
    from app.ar_pbr.gpu_preview import build_gpu_preview_items

    width = max(64, int(width))
    height = max(64, int(height))
    descriptor = _descriptor()
    camera = _camera(width, height)
    settings = {
        "asset_descriptors": {
            "qa_attachment_card.fbx": descriptor,
            "qa_ar_pbr_attachment": descriptor,
        },
        "camera_z": 3.25,
        "gpu_triangle_limit": 512,
    }
    anchors = [(0.38, 0.68), (0.50, 0.62), (0.62, 0.58)]
    frames: list[dict[str, Any]] = []
    max_error = 0.0
    total_triangles = 0
    total_shadow = 0
    total_reflection = 0
    placement_applied = 0
    for index, anchor in enumerate(anchors):
        items, diag = build_gpu_preview_items(
            frame_size=(width, height),
            time_ms=index * 500,
            ar_tracks=[_track(anchor)],
            camera_solution=camera,
            settings=settings,
        )
        center = _item_center_px(items[0], width, height) if items else None
        target = (anchor[0] * width, anchor[1] * height)
        error = math.inf if center is None else math.hypot(center[0] - target[0], center[1] - target[1])
        max_error = max(max_error, 9999.0 if not math.isfinite(error) else error)
        total_triangles += int(diag.get("triangle_count", 0) or 0)
        total_shadow += int(diag.get("shadow_triangle_count", 0) or 0)
        total_reflection += int(diag.get("reflection_triangle_count", 0) or 0)
        placement_applied += int(diag.get("placement_applied_count", 0) or 0)
        frames.append({
            "time_ms": index * 500,
            "target_px": [round(target[0], 3), round(target[1], 3)],
            "center_px": [round(center[0], 3), round(center[1], 3)] if center else None,
            "center_error_px": None if not math.isfinite(error) else round(error, 3),
            "triangle_count": int(diag.get("triangle_count", 0) or 0),
            "shadow_triangle_count": int(diag.get("shadow_triangle_count", 0) or 0),
            "reflection_triangle_count": int(diag.get("reflection_triangle_count", 0) or 0),
            "placement_applied_count": int(diag.get("placement_applied_count", 0) or 0),
            "warnings": list(diag.get("warnings", []) or []),
        })

    occluding_depth = np.zeros((height, width), dtype=np.float32)
    occluded_items, occluded_diag = build_gpu_preview_items(
        frame_size=(width, height),
        time_ms=1500,
        ar_tracks=[_track((0.5, 0.62), occlusion=True)],
        camera_solution=camera,
        depth_frame=occluding_depth,
        settings=settings,
    )
    occluded_triangles = int(occluded_diag.get("occluded_triangle_count", 0) or 0)
    visible_with_occluder = int(occluded_diag.get("visible_triangle_count", 0) or 0)
    tracking_transform = _tracking_transform_probe()
    checks = {
        "mesh_packets_generated": total_triangles >= len(anchors) * 2,
        "placement_applied_each_frame": placement_applied == len(anchors),
        "center_error_under_4px": max_error <= 4.0,
        "shadow_catcher_packets": total_shadow > 0,
        "reflection_catcher_packets": total_reflection > 0,
        "depth_occlusion_reduces_mesh": occluded_triangles > 0 and visible_with_occluder < 2,
        "video_affine_tracking_updates_scale_rotation": bool(tracking_transform.get("ok")),
    }
    ok = all(bool(value) for value in checks.values())
    return {
        "ok": ok,
        "frame_size": [width, height],
        "checks": checks,
        "frames": frames,
        "occlusion_probe": {
            "item_count": len(occluded_items),
            "visible_triangle_count": visible_with_occluder,
            "occluded_triangle_count": occluded_triangles,
            "diagnostics": occluded_diag,
        },
        "tracking_transform_probe": tracking_transform,
        "summary": {
            "frame_count": len(anchors),
            "max_center_error_px": round(max_error, 3),
            "triangle_count": total_triangles,
            "shadow_triangle_count": total_shadow,
            "reflection_triangle_count": total_reflection,
            "occluded_triangle_count": occluded_triangles,
            "tracked_scale_ratio": tracking_transform.get("scale_ratio"),
            "tracked_rotation_delta_deg": tracking_transform.get("rotation_delta_deg"),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--width", type=int, default=320)
    parser.add_argument("--height", type=int, default=180)
    args = parser.parse_args()

    report = run_qa(width=args.width, height=args.height)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
