from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _qimage_to_rgb_array(qimage) -> np.ndarray:
    from PySide6.QtGui import QImage

    converted = qimage.convertToFormat(QImage.Format.Format_RGBA8888)
    width = int(converted.width())
    height = int(converted.height())
    arr = np.empty((height, width, 3), dtype=np.uint8)
    # Qt's raw memory channel order can vary by platform/plugin even after
    # convertToFormat().  This QA is small and correctness matters more than
    # speed, so sample via QColor to match what QImage.save() would show.
    for y in range(height):
        for x in range(width):
            color = converted.pixelColor(x, y)
            arr[y, x, 0] = color.red()
            arr[y, x, 1] = color.green()
            arr[y, x, 2] = color.blue()
    return arr


def _make_base_frame(width: int, height: int) -> np.ndarray:
    yy, xx = np.mgrid[0:height, 0:width]
    r = 32 + (xx / max(1, width - 1) * 48).astype(np.uint8)
    g = 34 + (yy / max(1, height - 1) * 44).astype(np.uint8)
    b = np.full((height, width), 70, dtype=np.uint8)
    frame = np.dstack([r, g, b]).astype(np.uint8)
    frame[height // 3 : height * 2 // 3, width // 3 : width * 2 // 3, 1] = 105
    return np.ascontiguousarray(frame)


def _changed_pixels(a: np.ndarray, b: np.ndarray, threshold: int = 20) -> int:
    diff = np.abs(a.astype(np.int16) - b.astype(np.int16))
    return int(np.any(diff > int(threshold), axis=2).sum())


def _ar_pbr_test_item() -> dict[str, Any]:
    red = [1.0, 0.08, 0.02, 0.92]
    shadow = [0.0, 0.0, 0.0, 0.50]
    reflection = [0.22, 0.45, 1.0, 0.42]

    def v(x: float, y: float, rgba: list[float]) -> list[float]:
        return [float(x), float(y), *rgba]

    return {
        "kind": "qa_ndc_color_triangles",
        "shadow_vertices": [
            *v(-0.42, -0.62, shadow),
            *v(0.42, -0.62, shadow),
            *v(-0.32, -0.40, shadow),
            *v(-0.32, -0.40, shadow),
            *v(0.42, -0.62, shadow),
            *v(0.50, -0.40, shadow),
        ],
        "reflection_vertices": [
            *v(-0.30, -0.82, reflection),
            *v(0.30, -0.82, reflection),
            *v(-0.18, -0.64, reflection),
            *v(-0.18, -0.64, reflection),
            *v(0.30, -0.82, reflection),
            *v(0.18, -0.64, reflection),
        ],
        "vertices": [
            *v(-0.25, -0.25, red),
            *v(0.25, -0.25, red),
            *v(-0.25, 0.25, red),
            *v(-0.25, 0.25, red),
            *v(0.25, -0.25, red),
            *v(0.25, 0.25, red),
        ],
    }


def _ar_pbr_textured_pbr_test_item(asset_dir: Path, *, depth_occlusion: bool = False) -> dict[str, Any]:
    from PIL import Image

    asset_dir.mkdir(parents=True, exist_ok=True)
    base = asset_dir / "qa_pbr_base.png"
    roughness = asset_dir / "qa_pbr_roughness.png"
    metallic = asset_dir / "qa_pbr_metallic.png"
    specular = asset_dir / "qa_pbr_specular.png"
    normal = asset_dir / "qa_pbr_normal.png"
    if not base.exists():
        Image.new("RGB", (32, 32), (42, 220, 145)).save(base)
    if not roughness.exists():
        Image.new("L", (32, 32), 96).save(roughness)
    if not metallic.exists():
        Image.new("L", (32, 32), 18).save(metallic)
    if not specular.exists():
        Image.new("L", (32, 32), 205).save(specular)
    if not normal.exists():
        Image.new("RGB", (32, 32), (128, 128, 255)).save(normal)

    try:
        from app.ar_pbr.hdri_presets import default_hdri_path

        hdri_path = str(default_hdri_path())
    except Exception:
        hdri_path = ""

    normal_vec = (0.0, 0.0, -1.0)
    tangent = (1.0, 0.0, 0.0)
    bitangent = (0.0, 1.0, 0.0)
    rgba = (1.0, 1.0, 1.0, 0.96)
    pbr = (0.28, 0.05, 0.72)

    def pv(x: float, y: float, u: float, v: float) -> list[float]:
        return [
            float(x), float(y), float(u), float(v),
            *normal_vec,
            *tangent,
            *bitangent,
            *rgba,
            *pbr,
        ]

    verts = [
        *pv(-0.18, -0.15, 0.0, 0.0),
        *pv(0.34, -0.15, 1.0, 0.0),
        *pv(-0.18, 0.35, 0.0, 1.0),
        *pv(-0.18, 0.35, 0.0, 1.0),
        *pv(0.34, -0.15, 1.0, 0.0),
        *pv(0.34, 0.35, 1.0, 1.0),
    ]
    row: dict[str, Any] = {
        "kind": "qa_pbr_textured_triangles",
        "vertices": [],
        "shadow_vertices": [],
        "reflection_vertices": [],
        "pbr_triangle_count": 2,
        "pbr_triangles": [{
            "z": 3.0,
            "object_depth": 0.5,
            "texture": str(base),
            "maps": {
                "base": str(base),
                "roughness": str(roughness),
                "metallic": str(metallic),
                "specular": str(specular),
                "normal": str(normal),
            },
            "vertices": verts,
        }],
        "pbr_lighting": {
            "light_dir": [-0.35, -0.65, -0.72],
            "direct_strength": 1.1,
            "ibl_exposure": 1.2,
            "ibl_rotation": 0.0,
            "hdri_path": hdri_path,
        },
    }
    if depth_occlusion:
        depth = np.ones((180, 320), dtype=np.uint8) * 255
        depth[:, :160] = 0
        row["depth_texture"] = depth
        row["pbr_depth_occlusion"] = {
            "enabled": True,
            "tolerance": 0.02,
        }
    return row


def _derive_screenshot_path(screenshot: Path | None, suffix: str) -> Path | None:
    if screenshot is None:
        return None
    return screenshot.with_name(f"{screenshot.stem}_{suffix}{screenshot.suffix or '.png'}")


def _first_existing(candidates: list[Path]) -> Path | None:
    for path in candidates:
        if path.exists():
            return path
    return None


def _build_spine_preview_state(width: int, height: int) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    root = _repo_root()
    candidates = [
        root / "resources/spine_samples/chibi-stickers/export/chibi-stickers.json",
        root / "resources/spine_samples/arknights/amiya/build_char_002_amiya.json",
        root / "resources/spine_samples/celestial-circus/export/celestial-circus-pro.json",
    ]
    path = _first_existing(candidates)
    info: dict[str, Any] = {
        "ok": False,
        "status": "skipped",
        "path": str(path) if path else "",
        "error": "",
    }
    if path is None:
        info["error"] = "no spine sample found"
        return None, info
    try:
        from app.spine_editor.actor_track import SpineActorClip
        from app.spine_editor.spine_json_parser import load_spine_file
        from tools.test_spine_resources import _find_atlas, _pick_animation

        skeleton = load_spine_file(str(path))
        anim = _pick_animation(skeleton)
        atlas = _find_atlas(path)
        clip = SpineActorClip(
            skel_path=str(path),
            atlas_path=str(atlas) if atlas else "",
            anim_name=anim,
            start_ms=0,
            duration_ms=3000,
            pos_x=0.5,
            pos_y=0.5,
            scale=0.9,
        )
        state = clip.preview_render_state(width, height, 250, animated=True)
        if not state:
            info["status"] = "render_none"
            info["error"] = "preview_render_state returned None"
            return None, info
        info.update({
            "ok": True,
            "status": "ready",
            "animation": anim,
            "atlas": str(atlas) if atlas else "",
            "page_count": len(state.get("pil_pages") or []),
        })
        return state, info
    except Exception as exc:
        info["status"] = "error"
        info["error"] = f"{type(exc).__name__}: {exc}"
        return None, info


def _render_live2d_sample(width: int, height: int, output: Path) -> tuple[np.ndarray | None, dict[str, Any]]:
    root = _repo_root()
    candidates = [
        root / "resources/live2d_samples/CubismWebSamples/Samples/Resources/Haru/Haru.model3.json",
        root / "resources/live2d_samples/hiyori_free/hiyori_free_t08.model3.json",
        root / "resources/live2d_samples/CubismWebSamples/Samples/Resources/Hiyori/Hiyori.model3.json",
    ]
    path = _first_existing(candidates)
    info: dict[str, Any] = {
        "ok": False,
        "status": "skipped",
        "path": str(path) if path else "",
        "error": "",
    }
    if path is None:
        info["error"] = "no live2d sample found"
        return None, info
    try:
        from PIL import Image
        from tools.test_live2d_resources import run_one

        output.parent.mkdir(parents=True, exist_ok=True)
        result = run_one(path, width, height, 30, image_out=output)
        info.update(result)
        status = str(result.get("status") or "")
        if status != "pass" or not output.exists():
            info["ok"] = False
            return None, info
        rgba = Image.open(output).convert("RGBA")
        bg = Image.fromarray(_make_base_frame(width, height), "RGB").convert("RGBA")
        comp = Image.alpha_composite(bg, rgba)
        arr = np.asarray(comp.convert("RGB"), dtype=np.uint8)
        info["ok"] = True
        info["status"] = "ready"
        info["image_out"] = str(output)
        return np.ascontiguousarray(arr), info
    except Exception as exc:
        info["status"] = "error"
        info["error"] = f"{type(exc).__name__}: {exc}"
        return None, info


def _process_events(app, count: int = 8) -> None:
    from PySide6.QtTest import QTest

    for _ in range(max(1, int(count))):
        app.processEvents()
        QTest.qWait(20)


def _grab_nonempty_framebuffer(widget, app, *, attempts: int = 8):
    image = None
    for _ in range(max(1, int(attempts))):
        app.processEvents()
        try:
            widget.repaint()
        except Exception:
            pass
        _process_events(app, 1)
        try:
            image = widget.grabFramebuffer()
        except Exception:
            image = None
        if image is not None and int(image.width()) > 0 and int(image.height()) > 0:
            return image
    try:
        fallback = widget.grab().toImage()
        if int(fallback.width()) > 0 and int(fallback.height()) > 0:
            return fallback
    except Exception:
        pass
    return image


def run_gpu_preview_pixel_collision_qa(
    *,
    out: Path,
    screenshot: Path | None = None,
    visible: bool = False,
) -> dict[str, Any]:
    root = _repo_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from app.color_grading import ColorGrade
    from app.opengl_preview import OpenGLPreviewWidget

    app = QApplication.instance() or QApplication([])
    widget = OpenGLPreviewWidget()
    widget.resize(320, 180)
    widget.setWindowTitle("Tiger Studio GPU Preview QA")
    if not visible:
        widget.setWindowFlags(
            Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
        )
        widget.move(16, 16)
    widget.show()
    _process_events(app)

    report: dict[str, Any] = {
        "ok": False,
        "checks": {},
        "metrics": {},
        "covered": [
            "OpenGLPreviewWidget framebuffer capture",
            "color grade shader uniform path",
            "clip effect shader uniform path",
            "AR/PBR direct GL overlay packet path",
        ],
        "not_covered": [
            "full editor chrome/window screenshot interaction",
        ],
        "actor_checks": {},
        "skips": [],
        "errors": [],
    }
    try:
        base = _make_base_frame(160, 90)
        widget.set_clip_effects(None)
        widget.set_ar_pbr_overlay_items([])
        widget.update_frame(base, None)
        _process_events(app)
        baseline_image = _grab_nonempty_framebuffer(widget, app)
        if baseline_image is None or int(baseline_image.width()) <= 0 or int(baseline_image.height()) <= 0:
            raise RuntimeError("OpenGL framebuffer capture returned an empty image")
        baseline = _qimage_to_rgb_array(baseline_image)

        grade = ColorGrade(brightness=24, contrast=18, saturation=26, offset_x=20)
        widget.set_clip_effects(
            {
                "enabled": True,
                "filters": {
                    "sharpen": 0.25,
                    "vignette": 0.35,
                    "vignette_feather": 0.58,
                    "chroma_aberration": 0.0,
                },
                "chroma": None,
            }
        )
        widget.set_ar_pbr_overlay_items([_ar_pbr_test_item()])
        widget.update_frame(base, grade)
        _process_events(app)
        combined_image = _grab_nonempty_framebuffer(widget, app)
        if combined_image is None or int(combined_image.width()) <= 0 or int(combined_image.height()) <= 0:
            raise RuntimeError("OpenGL combined framebuffer capture returned an empty image")
        combined = _qimage_to_rgb_array(combined_image)

        if screenshot is not None:
            screenshot.parent.mkdir(parents=True, exist_ok=True)
            combined_image.save(str(screenshot))
            report["screenshot"] = str(screenshot)

        diff = np.abs(combined.astype(np.int16) - baseline.astype(np.int16))
        mean_diff = float(diff.mean())
        red_mask = (
            (combined[:, :, 0].astype(np.int16) > combined[:, :, 1].astype(np.int16) + 35)
            & (combined[:, :, 0].astype(np.int16) > combined[:, :, 2].astype(np.int16) + 35)
            & (combined[:, :, 0] > 100)
        )
        dark_mask = (
            combined[:, :, 0].astype(np.int16)
            + combined[:, :, 1].astype(np.int16)
            + combined[:, :, 2].astype(np.int16)
        ) < (
            baseline[:, :, 0].astype(np.int16)
            + baseline[:, :, 1].astype(np.int16)
            + baseline[:, :, 2].astype(np.int16)
            - 30
        )
        blue_mask = (
            (combined[:, :, 2].astype(np.int16) > combined[:, :, 0].astype(np.int16) + 20)
            & (combined[:, :, 2].astype(np.int16) > combined[:, :, 1].astype(np.int16) + 8)
            & (combined[:, :, 2] > 80)
        )

        widget.set_clip_effects(None)
        widget.set_ar_pbr_overlay_items([_ar_pbr_textured_pbr_test_item(out.parent / "qa_pbr_textures")])
        widget.set_spine_overlay_items([])
        widget.update_frame(base, None)
        _process_events(app)
        pbr_image = _grab_nonempty_framebuffer(widget, app)
        if pbr_image is None or int(pbr_image.width()) <= 0 or int(pbr_image.height()) <= 0:
            raise RuntimeError("OpenGL PBR framebuffer capture returned an empty image")
        pbr_frame = _qimage_to_rgb_array(pbr_image)
        pbr_diff = np.abs(pbr_frame.astype(np.int16) - baseline.astype(np.int16))
        pbr_changed = int(np.any(pbr_diff > 20, axis=2).sum())
        pbr_green_mask = (
            (pbr_frame[:, :, 1].astype(np.int16) > pbr_frame[:, :, 0].astype(np.int16) + 24)
            & (pbr_frame[:, :, 1].astype(np.int16) > pbr_frame[:, :, 2].astype(np.int16) + 8)
            & (pbr_frame[:, :, 1] > 90)
        )
        pbr_shot = _derive_screenshot_path(screenshot, "ar_pbr_pbr")
        if pbr_shot is not None:
            pbr_image.save(str(pbr_shot))
            report["pbr_screenshot"] = str(pbr_shot)

        widget.set_ar_pbr_overlay_items([_ar_pbr_textured_pbr_test_item(out.parent / "qa_pbr_textures", depth_occlusion=True)])
        widget.update_frame(base, None)
        _process_events(app)
        pbr_depth_image = _grab_nonempty_framebuffer(widget, app)
        if pbr_depth_image is None or int(pbr_depth_image.width()) <= 0 or int(pbr_depth_image.height()) <= 0:
            raise RuntimeError("OpenGL PBR depth framebuffer capture returned an empty image")
        pbr_depth_frame = _qimage_to_rgb_array(pbr_depth_image)
        pbr_depth_diff = np.abs(pbr_depth_frame.astype(np.int16) - baseline.astype(np.int16))
        pbr_depth_changed = int(np.any(pbr_depth_diff > 20, axis=2).sum())
        pbr_depth_shot = _derive_screenshot_path(screenshot, "ar_pbr_pbr_depth")
        if pbr_depth_shot is not None:
            pbr_depth_image.save(str(pbr_depth_shot))
            report["pbr_depth_screenshot"] = str(pbr_depth_shot)

        report["metrics"] = {
            "baseline_mean": float(baseline.mean()),
            "combined_mean": float(combined.mean()),
            "mean_abs_diff": mean_diff,
            "red_overlay_pixels": int(red_mask.sum()),
            "shadow_pixels": int(dark_mask.sum()),
            "blue_reflection_pixels": int(blue_mask.sum()),
            "pbr_textured_changed_pixels": int(pbr_changed),
            "pbr_textured_green_pixels": int(pbr_green_mask.sum()),
            "pbr_depth_occluded_changed_pixels": int(pbr_depth_changed),
            "framebuffer_size": [int(combined.shape[1]), int(combined.shape[0])],
        }
        checks = {
            "framebuffer_nonblank": bool(combined.max() > 0 and combined.mean() > 1.0),
            "shader_changed_base": bool(mean_diff >= 4.0),
            "ar_pbr_red_overlay_visible": bool(int(red_mask.sum()) >= 250),
            "shadow_or_reflection_visible": bool(
                int(dark_mask.sum()) >= 120 or int(blue_mask.sum()) >= 80
            ),
            "ar_pbr_textured_pbr_visible": bool(
                pbr_changed >= 180 and int(pbr_green_mask.sum()) >= 80
            ),
            "ar_pbr_pbr_depth_occlusion_visible": bool(
                pbr_depth_changed >= 80 and pbr_depth_changed < pbr_changed
            ),
        }
        report["checks"] = checks
        report["covered"].append("AR/PBR textured PBR shader path with base/roughness/metallic/specular/normal maps")
        report["covered"].append("AR/PBR live GL PBR depth-texture occlusion path")

        # Real actor samples: Spine uses the direct GL overlay path; Live2D is
        # rendered through the existing safe child-process renderer and then
        # uploaded as the GPU preview base frame, which matches the app's
        # CPU/prerender-then-GL-display contract.
        spine_state, spine_info = _build_spine_preview_state(160, 90)
        report["actor_checks"]["spine"] = spine_info
        if spine_state is not None:
            widget.set_clip_effects(None)
            widget.set_ar_pbr_overlay_items([])
            widget.set_spine_overlay_items([spine_state])
            widget.update_frame(base, None)
            _process_events(app)
            spine_image = _grab_nonempty_framebuffer(widget, app)
            spine_arr = _qimage_to_rgb_array(spine_image)
            spine_pixels = _changed_pixels(spine_arr, baseline, threshold=18)
            spine_shot = _derive_screenshot_path(screenshot, "spine")
            if spine_shot is not None:
                spine_image.save(str(spine_shot))
                spine_info["screenshot"] = str(spine_shot)
            spine_info["changed_pixels"] = int(spine_pixels)
            spine_info["visible"] = bool(spine_pixels >= 180)
            checks["spine_actor_visible"] = bool(spine_info["visible"])
            report["covered"].append("real Spine skeleton/atlas direct GL overlay path")
        else:
            report["skips"].append({"kind": "spine", **spine_info})
            report["not_covered"].append("real Spine direct GL overlay pixel QA skipped")

        live_image_path = _derive_screenshot_path(screenshot, "live2d_source")
        if live_image_path is None:
            live_image_path = out.parent / "gpu_preview_pixel_collision_live2d_source.png"
        live_rgb, live_info = _render_live2d_sample(160, 90, live_image_path)
        report["actor_checks"]["live2d"] = live_info
        if live_rgb is not None:
            widget.set_clip_effects(None)
            widget.set_ar_pbr_overlay_items([])
            widget.set_spine_overlay_items([])
            widget.update_frame(live_rgb, None)
            _process_events(app)
            live_frame = _grab_nonempty_framebuffer(widget, app)
            live_arr = _qimage_to_rgb_array(live_frame)
            live_pixels = _changed_pixels(live_arr, baseline, threshold=18)
            live_shot = _derive_screenshot_path(screenshot, "live2d")
            if live_shot is not None:
                live_frame.save(str(live_shot))
                live_info["screenshot"] = str(live_shot)
            live_info["changed_pixels"] = int(live_pixels)
            live_info["visible"] = bool(live_pixels >= 180)
            checks["live2d_actor_visible_after_gpu_upload"] = bool(live_info["visible"])
            report["covered"].append("real Live2D rendered frame uploaded through GPU preview base path")
        else:
            report["skips"].append({"kind": "live2d", **live_info})
            report["not_covered"].append("real Live2D GPU-display pixel QA skipped")

        report["checks"] = checks
        report["ok"] = all(checks.values())
    except Exception as exc:
        report["errors"].append(f"{type(exc).__name__}: {exc}")
    finally:
        widget.hide()
        widget.deleteLater()
        _process_events(app, 2)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Capture OpenGLPreviewWidget pixels and verify combined GPU preview payload visibility."
    )
    parser.add_argument(
        "--out",
        default=str(_repo_root() / "debugCapture" / "gpu_preview_pixel_collision_qa.json"),
        help="Report JSON path.",
    )
    parser.add_argument(
        "--screenshot",
        default=str(_repo_root() / "debugCapture" / "gpu_preview_pixel_collision.png"),
        help="Combined framebuffer screenshot path. Pass an empty string to disable.",
    )
    parser.add_argument(
        "--visible",
        action="store_true",
        help="Show the QA OpenGL widget instead of moving it off-screen.",
    )
    args = parser.parse_args(argv)
    out = Path(args.out)
    screenshot = Path(args.screenshot) if str(args.screenshot).strip() else None
    report = run_gpu_preview_pixel_collision_qa(
        out=out,
        screenshot=screenshot,
        visible=bool(args.visible),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
