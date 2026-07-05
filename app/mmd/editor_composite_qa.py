"""Editor preview/export composition QA for MMD actor overlays."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import numpy as np
from PIL import Image

from app.mmd.project_tracks import create_preview_mmd_track
from app.mmd.qa_corpus import DEFAULT_MMD_QA_MANIFEST, MMD_QA_PASS_STATUSES, resolve_mmd_qa_path
from app.project_player import ProjectPlayer


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MMD_EDITOR_COMPOSITE_QA_OUT_DIR = ROOT / "debugCapture" / "mmd_player" / "editor_composite_qa"
DEFAULT_MMD_EDITOR_COMPOSITE_QA_REPORT = ROOT / "debugCapture" / "mmd_player" / "mmd_editor_composite_qa.json"
DEFAULT_MMD_EDITOR_COMPOSITE_ENTRY_ID = "cantarella_wavefile_cloth_motion"


def _resolve_path(value: Any) -> Path | None:
    text = str(value or "").strip()
    if not text:
        return None
    path = Path(text)
    if path.is_absolute():
        return path
    return (ROOT / path).resolve()


def _load_manifest(manifest_path: str | Path) -> dict[str, Any]:
    resolved = resolve_mmd_qa_path(manifest_path)
    return json.loads(resolved.read_text(encoding="utf-8"))


def select_mmd_editor_composite_entry(
    manifest_path: str | Path = DEFAULT_MMD_QA_MANIFEST,
    *,
    entry_id: str = "",
) -> dict[str, Any]:
    """Pick a runnable MMD corpus entry for preview/export composition QA."""
    manifest = _load_manifest(manifest_path)
    entries = [row for row in list(manifest.get("entries") or []) if isinstance(row, dict)]
    if entry_id:
        for row in entries:
            if str(row.get("id") or "") == str(entry_id):
                return dict(row)
        raise ValueError(f"MMD QA corpus entry not found: {entry_id}")
    for row in entries:
        targets = {str(value) for value in list(row.get("qa_targets") or [])}
        if str(row.get("status") or "") in MMD_QA_PASS_STATUSES and "preview_export_parity" in targets:
            return dict(row)
    for row in entries:
        if str(row.get("status") or "") in MMD_QA_PASS_STATUSES:
            return dict(row)
    raise ValueError("No runnable MMD QA corpus entry found")


def _ensure_qapplication() -> None:
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication(sys.argv[:1])


def _write_synthetic_video(path: Path, *, width: int, height: int, fps: int, duration_ms: int) -> None:
    from imageio_ffmpeg import get_ffmpeg_exe
    from app.subprocess_utils import hidden_subprocess_kwargs

    path.parent.mkdir(parents=True, exist_ok=True)
    frames = max(1, int(round(max(1, duration_ms) / 1000.0 * max(1, fps))))
    cmd = [
        get_ffmpeg_exe(),
        "-y",
        "-f",
        "rawvideo",
        "-vcodec",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{width}x{height}",
        "-r",
        str(max(1, fps)),
        "-i",
        "pipe:0",
        "-an",
        "-vcodec",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(path),
    ]
    x = np.linspace(0.0, 1.0, width, dtype=np.float32)[None, :]
    y = np.linspace(0.0, 1.0, height, dtype=np.float32)[:, None]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE, **hidden_subprocess_kwargs())
    assert proc.stdin is not None
    try:
        for frame_idx in range(frames):
            t = float(frame_idx) / float(max(1, frames - 1))
            frame = np.zeros((height, width, 3), dtype=np.uint8)
            frame[:, :, 0] = np.clip(32 + 90 * x + 24 * t, 0, 255).astype(np.uint8)
            frame[:, :, 1] = np.clip(42 + 72 * (1.0 - y) + 20 * np.sin(t * np.pi), 0, 255).astype(np.uint8)
            frame[:, :, 2] = np.clip(54 + 62 * y + 34 * (1.0 - x), 0, 255).astype(np.uint8)
            frame[:, width // 2 - 1 : width // 2 + 1, :] = np.asarray((225, 232, 248), dtype=np.uint8)
            frame[height // 2 - 1 : height // 2 + 1, :, :] = np.asarray((28, 34, 48), dtype=np.uint8)
            proc.stdin.write(np.ascontiguousarray(frame).tobytes())
        proc.stdin.close()
        err = proc.stderr.read() if proc.stderr is not None else b""
        rc = proc.wait()
    finally:
        try:
            if proc.stdin is not None and not proc.stdin.closed:
                proc.stdin.close()
        except OSError:
            pass
    if rc != 0 or not path.exists() or path.stat().st_size <= 0:
        message = err.decode("utf-8", errors="replace")[-400:] if err else ""
        raise RuntimeError(f"Could not write MMD composite QA source video: {message}")


def _read_video_frame(path: Path, *, frame_index: int) -> dict[str, Any]:
    import cv2  # type: ignore

    cap = cv2.VideoCapture(str(path))
    if not cap or not cap.isOpened():
        return {"ok": False, "error": "open_failed", "path": str(path)}
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    idx = max(0, min(int(frame_index), max(0, frames - 1)))
    if frames > 0:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
    ok, bgr = cap.read()
    cap.release()
    if not ok or bgr is None:
        return {
            "ok": False,
            "error": "frame_read_failed",
            "frames": frames,
            "fps": fps,
            "width": width,
            "height": height,
        }
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    return {
        "ok": True,
        "rgb": rgb,
        "frames": frames,
        "fps": round(float(fps), 3),
        "width": width,
        "height": height,
        "frame_index": idx,
    }


def _alpha_metrics(rgba: np.ndarray) -> dict[str, Any]:
    if rgba is None or rgba.ndim != 3 or rgba.shape[2] < 4:
        return {"ok": False, "reason": "missing_rgba"}
    h, w = int(rgba.shape[0]), int(rgba.shape[1])
    alpha = np.asarray(rgba[:, :, 3], dtype=np.uint8)
    mask = alpha > 8
    alpha_max = int(alpha.max()) if alpha.size else 0
    coverage = float(np.count_nonzero(mask)) / float(max(1, w * h))
    if not np.any(mask):
        return {"ok": False, "reason": "blank_alpha", "alpha_max": alpha_max, "alpha_coverage": coverage}
    ys, xs = np.nonzero(mask)
    bbox = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
    return {
        "ok": bool(alpha_max > 0 and coverage > 0.002),
        "reason": "" if alpha_max > 0 and coverage > 0.002 else "low_alpha_coverage",
        "alpha_max": alpha_max,
        "alpha_coverage": coverage,
        "bbox": bbox,
    }


def _composite_delta_metrics(baseline_rgb: np.ndarray, composite_rgb: np.ndarray, overlay_rgba: np.ndarray) -> dict[str, Any]:
    if baseline_rgb.shape != composite_rgb.shape:
        return {"ok": False, "error": "frame_shape_mismatch"}
    alpha = np.asarray(overlay_rgba[:, :, 3], dtype=np.uint8)
    mask = alpha > 8
    if not np.any(mask):
        return {"ok": False, "error": "blank_overlay_alpha"}
    delta = np.abs(composite_rgb.astype(np.int16) - baseline_rgb.astype(np.int16))
    pixel_delta = np.mean(delta, axis=2)
    h, w = alpha.shape[:2]
    ys, xs = np.nonzero(mask)
    pad = max(6, min(w, h) // 32)
    x0 = max(0, int(xs.min()) - pad)
    x1 = min(w, int(xs.max()) + pad + 1)
    y0 = max(0, int(ys.min()) - pad)
    y1 = min(h, int(ys.max()) + pad + 1)
    bbox_mask = np.zeros((h, w), dtype=bool)
    bbox_mask[y0:y1, x0:x1] = True
    outside_mask = ~bbox_mask
    inside_mean = float(pixel_delta[mask].mean()) if np.any(mask) else 0.0
    bbox_mean = float(pixel_delta[bbox_mask].mean()) if np.any(bbox_mask) else 0.0
    outside_mean = float(pixel_delta[outside_mask].mean()) if np.any(outside_mask) else 0.0
    changed_ratio = float(np.count_nonzero(pixel_delta > 10.0)) / float(max(1, w * h))
    outside_changed_ratio = (
        float(np.count_nonzero(pixel_delta[outside_mask] > 10.0)) / float(max(1, np.count_nonzero(outside_mask)))
        if np.any(outside_mask)
        else 0.0
    )
    isolation_ratio = inside_mean / max(0.001, outside_mean)
    ok = inside_mean > 3.0 and changed_ratio > 0.002 and outside_mean < 6.0 and isolation_ratio > 1.2
    return {
        "ok": bool(ok),
        "inside_mean_abs_diff": round(inside_mean, 4),
        "bbox_mean_abs_diff": round(bbox_mean, 4),
        "outside_mean_abs_diff": round(outside_mean, 4),
        "changed_pixel_ratio": round(changed_ratio, 5),
        "outside_changed_pixel_ratio": round(outside_changed_ratio, 5),
        "isolation_ratio": round(isolation_ratio, 4),
        "comparison_bbox": [x0, y0, x1 - 1, y1 - 1],
    }


def _save_rgb(path: Path, rgb: np.ndarray) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.ascontiguousarray(rgb[:, :, :3], dtype=np.uint8), "RGB").save(path)
    return str(path)


def _save_rgba(path: Path, rgba: np.ndarray) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.ascontiguousarray(rgba[:, :, :4], dtype=np.uint8), "RGBA").save(path)
    return str(path)


def _run_export(exporter: Any) -> dict[str, Any]:
    events: dict[str, Any] = {"success": None, "error": ""}

    def _success(path: Path, size: int) -> None:
        events["success"] = {"path": str(path), "size": int(size)}

    def _error(message: str) -> None:
        events["error"] = str(message)

    exporter.finished_success.connect(_success)
    exporter.finished_error.connect(_error)
    exporter.run()
    try:
        exporter.deleteLater()
    except Exception:
        pass
    events["ok"] = bool(events.get("success")) and not bool(events.get("error"))
    return events


def _entry_paths(entry: Mapping[str, Any]) -> tuple[Path, Path | None]:
    model_path = _resolve_path(entry.get("model_path"))
    motion_path = _resolve_path(entry.get("motion_path"))
    if model_path is None or not model_path.exists():
        raise FileNotFoundError(f"MMD model not found: {model_path}")
    if motion_path is not None and not motion_path.exists():
        raise FileNotFoundError(f"MMD motion not found: {motion_path}")
    return model_path, motion_path


def run_mmd_editor_composite_qa(
    *,
    manifest: str | Path = DEFAULT_MMD_QA_MANIFEST,
    entry_id: str = DEFAULT_MMD_EDITOR_COMPOSITE_ENTRY_ID,
    out_dir: str | Path = DEFAULT_MMD_EDITOR_COMPOSITE_QA_OUT_DIR,
    report_path: str | Path = DEFAULT_MMD_EDITOR_COMPOSITE_QA_REPORT,
    width: int = 320,
    height: int = 180,
    duration_ms: int = 1000,
    fps: int = 12,
    sample_time_ms: int | None = None,
) -> dict[str, Any]:
    """Run a small MMD-over-video preview/export smoke QA."""
    from app.video_exporter import VideoExportThread
    from app.mmd.offscreen_export import MMDOffscreenGLRenderer

    _ensure_qapplication()
    resolved_manifest = resolve_mmd_qa_path(manifest)
    out = Path(out_dir).expanduser().resolve()
    report = Path(report_path).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    width = max(160, int(width or 320))
    height = max(120, int(height or 180))
    duration_ms = max(500, int(duration_ms or 1000))
    fps = max(4, min(60, int(fps or 12)))
    sample_ms = max(0, min(duration_ms - 1, int(sample_time_ms if sample_time_ms is not None else duration_ms // 2)))
    sample_frame_index = max(0, int(round(sample_ms / 1000.0 * fps)))

    entry = select_mmd_editor_composite_entry(resolved_manifest, entry_id=entry_id)
    model_path, motion_path = _entry_paths(entry)
    source = out / "mmd_composite_source.mp4"
    baseline = out / "mmd_composite_baseline.mp4"
    final = out / "mmd_composite_export.mp4"
    for path in (source, baseline, final):
        try:
            path.unlink()
        except OSError:
            pass
    _write_synthetic_video(source, width=width, height=height, fps=fps, duration_ms=duration_ms)

    track = create_preview_mmd_track(
        model_path,
        track_id="mmd_composite_001",
        start_ms=0,
        duration_ms=duration_ms,
        motion_path=motion_path,
    )
    track["end_ms"] = duration_ms
    track["duration_ms"] = duration_ms
    tracks = [track]

    player = ProjectPlayer()
    renderer = MMDOffscreenGLRenderer()
    try:
        player.set_mmd_tracks(tracks)
        items = player._mmd_overlay_items(sample_ms, animate=True)
        overlay_rgba = renderer.render_array(items, width, height) if items else None
    finally:
        player.release()
    if overlay_rgba is None:
        overlay_rgba = np.zeros((height, width, 4), dtype=np.uint8)
    overlay_rgba = np.ascontiguousarray(overlay_rgba[:, :, :4], dtype=np.uint8)
    alpha = _alpha_metrics(overlay_rgba)

    source_probe = _read_video_frame(source, frame_index=sample_frame_index)
    if not bool(source_probe.get("ok")):
        raise RuntimeError(f"Could not read synthetic source frame: {source_probe.get('error')}")
    source_rgb = np.asarray(source_probe["rgb"], dtype=np.uint8)
    preview_rgb = ProjectPlayer._alpha_composite_rgba_array(source_rgb, overlay_rgba)
    preview_delta = _composite_delta_metrics(source_rgb, preview_rgb, overlay_rgba)

    segments = [(0, duration_ms, 1.0)]
    overlay_specs = VideoExportThread.pre_render_mmd_actors(
        tracks,
        source_path=str(source),
        fps=fps,
        segments=segments,
        frame_size=(width, height),
    )
    pre_render = {
        "ok": bool(overlay_specs),
        "overlay_count": int(len(overlay_specs)),
        "overlay_sizes": [
            int(Path(path).stat().st_size) if Path(path).exists() else 0
            for path, _start, _end in overlay_specs
        ],
    }

    baseline_result = _run_export(
        VideoExportThread(
            source,
            baseline,
            segments,
            quality_id="low",
            format_id="mp4",
            target_fps=float(fps),
        )
    )
    final_result = _run_export(
        VideoExportThread(
            source,
            final,
            segments,
            quality_id="low",
            format_id="mp4",
            target_fps=float(fps),
            mmd_tracks=tracks,
            mmd_pre_rendered=overlay_specs,
        )
    )

    baseline_probe = _read_video_frame(baseline, frame_index=sample_frame_index) if baseline.exists() else {"ok": False, "error": "missing_baseline"}
    final_probe = _read_video_frame(final, frame_index=sample_frame_index) if final.exists() else {"ok": False, "error": "missing_final"}
    if bool(baseline_probe.get("ok")) and bool(final_probe.get("ok")):
        export_delta = _composite_delta_metrics(
            np.asarray(baseline_probe["rgb"], dtype=np.uint8),
            np.asarray(final_probe["rgb"], dtype=np.uint8),
            overlay_rgba,
        )
    else:
        export_delta = {"ok": False, "error": "missing_export_frame"}

    outputs = {
        "source": str(source),
        "baseline_video": str(baseline),
        "export_video": str(final),
        "preview_composite": _save_rgb(out / "mmd_composite_preview.png", preview_rgb),
        "preview_overlay_rgba": _save_rgba(out / "mmd_composite_overlay.png", overlay_rgba),
    }
    if bool(baseline_probe.get("ok")):
        outputs["baseline_frame"] = _save_rgb(out / "mmd_composite_baseline_frame.png", np.asarray(baseline_probe["rgb"], dtype=np.uint8))
    if bool(final_probe.get("ok")):
        outputs["export_frame"] = _save_rgb(out / "mmd_composite_export_frame.png", np.asarray(final_probe["rgb"], dtype=np.uint8))

    checks = {
        "preview_mmd_alpha_visible": bool(alpha.get("ok")),
        "preview_composite_changes_mmd_region": bool(preview_delta.get("ok")),
        "mmd_prerender_alpha_mov_created": bool(pre_render.get("ok")) and any(size > 4096 for size in pre_render.get("overlay_sizes", [])),
        "baseline_export_ok": bool(baseline_result.get("ok")) and baseline.exists() and baseline.stat().st_size > 4096,
        "mmd_export_ok": bool(final_result.get("ok")) and final.exists() and final.stat().st_size > 4096,
        "export_composite_changes_mmd_region": bool(export_delta.get("ok")),
    }
    failures = [{"check": key, "message": "check failed"} for key, value in checks.items() if not value]
    payload = {
        "ok": not failures,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "kind": "mmd_editor_composite_qa",
        "manifest": str(resolved_manifest),
        "entry_id": str(entry.get("id") or ""),
        "model_path": str(model_path),
        "motion_path": str(motion_path or ""),
        "width": width,
        "height": height,
        "duration_ms": duration_ms,
        "fps": fps,
        "sample_time_ms": sample_ms,
        "sample_frame_index": sample_frame_index,
        "checks": checks,
        "summary": {
            "checks": len(checks),
            "passing": sum(1 for value in checks.values() if value),
            "failing": len(failures),
            "alpha_coverage": alpha.get("alpha_coverage", 0.0),
            "preview_inside_mean_abs_diff": preview_delta.get("inside_mean_abs_diff", 0.0),
            "export_inside_mean_abs_diff": export_delta.get("inside_mean_abs_diff", 0.0),
            "export_outside_mean_abs_diff": export_delta.get("outside_mean_abs_diff", 0.0),
        },
        "alpha_metrics": alpha,
        "preview_delta": preview_delta,
        "export_delta": export_delta,
        "pre_render": pre_render,
        "baseline_export": baseline_result,
        "mmd_export": final_result,
        "baseline_probe": {k: v for k, v in baseline_probe.items() if k != "rgb"},
        "final_probe": {k: v for k, v in final_probe.items() if k != "rgb"},
        "outputs": outputs,
        "failures": failures,
    }
    report.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    payload["report"] = str(report)
    return payload
