"""Render visual QA PNGs for the local MMD QA corpus."""
from __future__ import annotations

from pathlib import Path
import argparse
import json
import sys
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from PySide6.QtGui import QGuiApplication

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.mmd.animation import MMDPoseGeometry, evaluate_model_pose
from app.mmd.framing import auto_frame_bounds, bounds_from_positions
from app.mmd.gpu_preview import MMD_GPU_MORPH_SLOTS, build_mmd_render_item
from app.mmd.loader import load_mmd_model
from app.mmd.offscreen_export import MMDOffscreenGLRenderer
from app.mmd.physics import SpringPhysicsBackend
from app.mmd.vmd import VMDMotion, camera_at, camera_to_view_controls, load_vmd


DEFAULT_MANIFEST = ROOT / "local_resources" / "mmd" / "qa_corpus_manifest.json"
DEFAULT_OUT_DIR = ROOT / "debugCapture" / "mmd_player" / "qa_corpus_visual"
PASS_STATUSES = {"ready", "verified", "candidate"}
DEFAULT_WIDTH = 960
DEFAULT_HEIGHT = 540


def _resolve_path(value: Any) -> Path | None:
    text = str(value or "").strip()
    if not text:
        return None
    path = Path(text)
    if path.is_absolute():
        return path
    return (ROOT / path).resolve()


def _load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _entry_capture_time_ms(entry: dict[str, Any], motion: VMDMotion | None) -> int:
    visual = entry.get("visual_capture")
    if isinstance(visual, dict) and visual.get("time_ms") is not None:
        try:
            return max(0, int(visual.get("time_ms")))
        except Exception:
            pass
    entry_id = str(entry.get("id") or "")
    if "run_walk" in entry_id or "walk" in entry_id:
        return 800
    if motion is None or int(motion.max_frame) <= 0:
        return 0
    return min(2600, int(round((float(motion.max_frame) / 30.0) * 1000.0 * 0.65)))


def _frame_from_ms(time_ms: int, motion: VMDMotion | None) -> float:
    frame = max(0.0, float(time_ms) / 1000.0 * 30.0)
    if motion is not None and int(motion.max_frame) > 0:
        frame = min(frame, float(motion.max_frame))
    return frame


def _evaluate_temporal_pose(
    model: Any,
    motion: VMDMotion | None,
    frame: float,
    *,
    skin_vertices: bool,
    gpu_morph_slots: int,
) -> MMDPoseGeometry:
    backend = SpringPhysicsBackend()
    warmup = sorted(set(round(value, 4) for value in (0.0, max(0.0, frame - 18.0), frame)))
    pose: MMDPoseGeometry | None = None
    for sample in warmup:
        pose = evaluate_model_pose(
            model,
            motion,
            sample,
            physics_backend=backend,
            enable_ik=True,
            enable_physics=True,
            max_ik_iterations=6,
            skin_vertices=skin_vertices,
            gpu_morph_slots=gpu_morph_slots,
        )
    if pose is None:
        pose = evaluate_model_pose(model, motion, frame)
    return pose


def _background(width: int, height: int) -> np.ndarray:
    y = np.linspace(0.0, 1.0, height, dtype=np.float32)[:, None]
    x = np.linspace(0.0, 1.0, width, dtype=np.float32)[None, :]
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:, :, 0] = np.clip(18 + 24 * (1.0 - y) + 8 * x, 0, 255).astype(np.uint8)
    frame[:, :, 1] = np.clip(19 + 25 * (1.0 - y) + 5 * x, 0, 255).astype(np.uint8)
    frame[:, :, 2] = np.clip(22 + 30 * (1.0 - y) + 12 * x, 0, 255).astype(np.uint8)
    floor = int(height * 0.72)
    frame[floor:, :, :] = np.asarray((24, 25, 28), dtype=np.uint8)
    return np.ascontiguousarray(frame)


def _composite_rgba(rgba: np.ndarray, width: int, height: int) -> np.ndarray:
    bg = _background(width, height).astype(np.float32)
    if rgba.ndim != 3 or rgba.shape[2] < 4:
        return bg.astype(np.uint8)
    fg = rgba[:, :, :3].astype(np.float32)
    alpha = np.clip(rgba[:, :, 3:4].astype(np.float32) / 255.0, 0.0, 1.0)
    return np.clip(fg * alpha + bg * (1.0 - alpha), 0, 255).astype(np.uint8)


def _visual_metrics_from_rgba(rgba: np.ndarray) -> dict[str, Any]:
    if rgba is None or rgba.ndim != 3 or rgba.shape[2] < 4:
        return {"ok": False, "reason": "missing_rgba"}
    h, w = int(rgba.shape[0]), int(rgba.shape[1])
    alpha = np.asarray(rgba[:, :, 3], dtype=np.uint8)
    mask = alpha > 8
    coverage = float(np.count_nonzero(mask)) / float(max(1, w * h))
    alpha_max = int(alpha.max()) if alpha.size else 0
    if not np.any(mask):
        return {
            "ok": False,
            "reason": "blank_alpha",
            "alpha_max": alpha_max,
            "alpha_coverage": coverage,
        }
    ys, xs = np.nonzero(mask)
    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())
    margins = {
        "left": x0,
        "right": max(0, w - 1 - x1),
        "top": y0,
        "bottom": max(0, h - 1 - y1),
    }
    touches_edge = any(value <= 1 for value in margins.values())
    too_small = coverage < 0.006
    too_large = coverage > 0.82
    return {
        "ok": bool(alpha_max > 0 and not touches_edge and not too_small and not too_large),
        "reason": "" if alpha_max > 0 and not touches_edge and not too_small and not too_large else "visual_bounds_warning",
        "alpha_max": alpha_max,
        "alpha_coverage": coverage,
        "bbox": [x0, y0, x1, y1],
        "margins": margins,
        "touches_edge": bool(touches_edge),
        "too_small": bool(too_small),
        "too_large": bool(too_large),
    }


def _camera_controls(
    pose: MMDPoseGeometry,
    camera_motion: VMDMotion | None,
    frame: float,
    *,
    width: int,
    height: int,
) -> dict[str, float]:
    yaw = 0.0
    pitch = -4.0
    roll = 0.0
    bounds = bounds_from_positions(pose.positions, trim_percentile=1.0)
    fit = auto_frame_bounds(bounds, yaw=yaw, pitch=pitch, roll=roll, aspect=float(width) / float(max(1, height)))
    camera = camera_at(camera_motion, frame)
    if camera is None:
        return fit.to_camera_controls(yaw=yaw, pitch=pitch, roll=roll)
    return camera_to_view_controls(
        camera,
        fallback_yaw=yaw,
        fallback_pitch=pitch,
        fallback_zoom=fit.zoom,
        fallback_offset_x=fit.offset_x,
        fallback_offset_y=fit.offset_y,
    )


def _render_entry(
    renderer: MMDOffscreenGLRenderer,
    entry: dict[str, Any],
    out_dir: Path,
    *,
    width: int,
    height: int,
    use_gpu_skinning: bool,
) -> dict[str, Any]:
    entry_id = str(entry.get("id") or "mmd_entry")
    model_path = _resolve_path(entry.get("model_path"))
    motion_path = _resolve_path(entry.get("motion_path"))
    visual = entry.get("visual_capture") if isinstance(entry.get("visual_capture"), dict) else {}
    use_camera_motion = bool(visual.get("use_camera_motion", False))
    camera_motion_path = _resolve_path(entry.get("camera_motion_path")) if use_camera_motion else None
    if model_path is None or not model_path.exists():
        return {"id": entry_id, "ok": False, "error": "missing_model_path", "path": str(model_path or "")}
    if motion_path is not None and not motion_path.exists():
        return {"id": entry_id, "ok": False, "error": "missing_motion_path", "path": str(motion_path)}
    if camera_motion_path is not None and not camera_motion_path.exists():
        return {"id": entry_id, "ok": False, "error": "missing_camera_motion_path", "path": str(camera_motion_path)}

    model = load_mmd_model(model_path)
    motion = load_vmd(motion_path) if motion_path is not None else None
    camera_motion = load_vmd(camera_motion_path) if camera_motion_path is not None else (motion if use_camera_motion else None)
    time_ms = _entry_capture_time_ms(entry, motion)
    frame = _frame_from_ms(time_ms, motion)
    bounds_pose = _evaluate_temporal_pose(model, motion, frame, skin_vertices=True, gpu_morph_slots=0)
    render_pose = bounds_pose
    if use_gpu_skinning and not np.any(np.asarray(model.weights.weight_types, dtype=np.uint8) == 3):
        render_pose = _evaluate_temporal_pose(
            model,
            motion,
            frame,
            skin_vertices=False,
            gpu_morph_slots=MMD_GPU_MORPH_SLOTS,
        )
    controls = _camera_controls(bounds_pose, camera_motion, frame, width=width, height=height)
    item = build_mmd_render_item(
        model,
        pose_geometry=render_pose,
        camera_controls=controls,
        lighting_preset=str(visual.get("lighting") or "studio_soft"),
        bloom_strength=float(visual.get("bloom", 0.35)),
    )
    rgba = renderer.render_array([item], width, height)
    if rgba is None:
        return {"id": entry_id, "ok": False, "error": "offscreen_renderer_unavailable"}
    metrics = _visual_metrics_from_rgba(rgba)
    rgb = _composite_rgba(rgba, width, height)
    out_path = out_dir / f"{entry_id}.png"
    Image.fromarray(rgb, "RGB").save(out_path)
    return {
        "id": entry_id,
        "ok": bool(metrics.get("ok")),
        "status": str(entry.get("status") or ""),
        "model_path": str(model_path),
        "motion_path": str(motion_path or ""),
        "screenshot": str(out_path),
        "time_ms": int(time_ms),
        "frame": float(frame),
        "gpu_skinning": bool(item.get("gpu_skinning")),
        "camera_motion_used": bool(use_camera_motion),
        "diagnostics": dict(item.get("diagnostics") or {}),
        "visual_metrics": metrics,
    }


def _font(size: int) -> ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ]
    for path in candidates:
        try:
            if path.exists():
                return ImageFont.truetype(str(path), size=size)
        except Exception:
            pass
    return ImageFont.load_default()


def _write_contact_sheet(results: list[dict[str, Any]], out_path: Path) -> None:
    images: list[tuple[dict[str, Any], Image.Image]] = []
    for result in results:
        path = Path(str(result.get("screenshot") or ""))
        if path.exists():
            images.append((result, Image.open(path).convert("RGB")))
    if not images:
        return
    cell_w, cell_h = 480, 328
    thumb_w, thumb_h = 480, 270
    cols = 2
    rows = int(np.ceil(len(images) / cols))
    sheet = Image.new("RGB", (cell_w * cols, cell_h * rows), (18, 19, 22))
    draw = ImageDraw.Draw(sheet)
    title_font = _font(16)
    small_font = _font(12)
    for index, (result, image) in enumerate(images):
        col = index % cols
        row = index // cols
        x = col * cell_w
        y = row * cell_h
        thumb = image.resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
        sheet.paste(thumb, (x, y))
        ok = bool(result.get("ok"))
        label = f"{result.get('id')}  {'OK' if ok else 'CHECK'}"
        metrics = result.get("visual_metrics") if isinstance(result.get("visual_metrics"), dict) else {}
        coverage = float(metrics.get("alpha_coverage", 0.0) or 0.0)
        gpu = "GPU" if result.get("gpu_skinning") else "CPU"
        draw.rectangle((x, y + thumb_h, x + cell_w, y + cell_h), fill=(23, 24, 29))
        draw.text((x + 10, y + thumb_h + 8), label, font=title_font, fill=(220, 236, 230) if ok else (255, 205, 132))
        draw.text(
            (x + 10, y + thumb_h + 32),
            f"{gpu}  frame {float(result.get('frame', 0.0)):.1f}  alpha {coverage:.3f}",
            font=small_font,
            fill=(164, 174, 190),
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)


def run_visual_corpus(
    manifest_path: Path,
    out_dir: Path,
    *,
    width: int,
    height: int,
    use_gpu_skinning: bool,
) -> dict[str, Any]:
    manifest = _load_manifest(manifest_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
    renderer = MMDOffscreenGLRenderer()
    results: list[dict[str, Any]] = []
    for raw in list(manifest.get("entries") or []):
        if not isinstance(raw, dict):
            continue
        if str(raw.get("status") or "") not in PASS_STATUSES:
            continue
        results.append(
            _render_entry(
                renderer,
                raw,
                out_dir,
                width=width,
                height=height,
                use_gpu_skinning=use_gpu_skinning,
            )
        )
    contact_sheet = out_dir / "mmd_qa_visual_contact_sheet.png"
    _write_contact_sheet(results, contact_sheet)
    payload = {
        "ok": all(bool(result.get("ok")) for result in results),
        "manifest": str(manifest_path),
        "out_dir": str(out_dir),
        "contact_sheet": str(contact_sheet),
        "run_count": int(len(results)),
        "width": int(width),
        "height": int(height),
        "gpu_skinning_requested": bool(use_gpu_skinning),
        "results": results,
        "blocked_entries": list(manifest.get("blocked_entries") or []),
    }
    report_path = out_dir / "mmd_qa_visual_report.json"
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    payload["report"] = str(report_path)
    return payload


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    parser = argparse.ArgumentParser(description="Render visual QA PNGs for the MMD corpus")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH)
    parser.add_argument("--height", type=int, default=DEFAULT_HEIGHT)
    parser.add_argument("--cpu-skinning", action="store_true", help="Use CPU-skinned geometry for screenshots")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    payload = run_visual_corpus(
        _resolve_path(args.manifest) or DEFAULT_MANIFEST,
        _resolve_path(args.out_dir) or DEFAULT_OUT_DIR,
        width=max(160, int(args.width)),
        height=max(120, int(args.height)),
        use_gpu_skinning=not bool(args.cpu_skinning),
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"ok            : {bool(payload.get('ok'))}")
        print(f"run_count     : {int(payload.get('run_count', 0) or 0)}")
        print(f"contact_sheet : {payload.get('contact_sheet')}")
        print(f"report        : {payload.get('report')}")
        for result in list(payload.get("results") or []):
            metrics = result.get("visual_metrics") if isinstance(result.get("visual_metrics"), dict) else {}
            print(
                f"{result.get('id'):<34} ok={bool(result.get('ok'))} "
                f"gpu={bool(result.get('gpu_skinning'))} "
                f"alpha={float(metrics.get('alpha_coverage', 0.0) or 0.0):.3f} "
                f"shot={result.get('screenshot')}"
            )
    return 0 if bool(payload.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
