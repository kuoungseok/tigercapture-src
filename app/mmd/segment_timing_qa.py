"""Segment trim/speed QA for MMD actor export timing."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from app.mmd.editor_composite_qa import (
    DEFAULT_MMD_EDITOR_COMPOSITE_ENTRY_ID,
    _alpha_metrics,
    _composite_delta_metrics,
    _ensure_qapplication,
    _entry_paths,
    _read_video_frame,
    _run_export,
    _save_rgb,
    _save_rgba,
    _write_synthetic_video,
    select_mmd_editor_composite_entry,
)
from app.mmd.project_tracks import create_preview_mmd_track
from app.mmd.qa_corpus import DEFAULT_MMD_QA_MANIFEST, resolve_mmd_qa_path
from app.mmd.timeline_qa import (
    _active_track_ids,
    _inactive_delta_metrics,
    _probe_without_rgb,
    _project_ms_for_output_ms,
    _sample_frame_index,
    _source_frame_index,
    _strip_rgb_from_probe,
)
from app.project_player import ProjectPlayer


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MMD_SEGMENT_TIMING_QA_OUT_DIR = ROOT / "debugCapture" / "mmd_player" / "segment_timing_qa"
DEFAULT_MMD_SEGMENT_TIMING_QA_REPORT = ROOT / "debugCapture" / "mmd_player" / "mmd_segment_timing_qa.json"
DEFAULT_MMD_SEGMENT_TIMING_ENTRY_ID = DEFAULT_MMD_EDITOR_COMPOSITE_ENTRY_ID


def _make_segment_tracks(model_path: Path, motion_path: Path | None, *, duration_ms: int) -> list[dict[str, Any]]:
    track_a = create_preview_mmd_track(
        model_path,
        track_id="mmd_segment_a",
        start_ms=250,
        duration_ms=400,
        motion_path=motion_path,
    )
    track_a["end_ms"] = min(int(duration_ms), 650)
    track_a["duration_ms"] = max(1, int(track_a["end_ms"]) - int(track_a["start_ms"]))
    track_a["view"].update({"offset_x": -0.24, "offset_y": 0.02, "zoom": 0.62})
    track_a["render"]["bloom_strength"] = 0.22

    gap_track = create_preview_mmd_track(
        model_path,
        track_id="mmd_segment_gap_only",
        start_ms=980,
        duration_ms=200,
        motion_path=motion_path,
    )
    gap_track["end_ms"] = min(int(duration_ms), 1180)
    gap_track["duration_ms"] = max(1, int(gap_track["end_ms"]) - int(gap_track["start_ms"]))
    gap_track["view"].update({"offset_x": 0.0, "offset_y": 0.02, "zoom": 0.72})
    gap_track["render"]["bloom_strength"] = 0.50

    track_b = create_preview_mmd_track(
        model_path,
        track_id="mmd_segment_b",
        start_ms=1550,
        duration_ms=550,
        motion_path=motion_path,
    )
    track_b["end_ms"] = min(int(duration_ms), 2100)
    track_b["duration_ms"] = max(1, int(track_b["end_ms"]) - int(track_b["start_ms"]))
    track_b["view"].update({"offset_x": 0.26, "offset_y": 0.02, "zoom": 0.62})
    track_b["playback"]["motion_start_ms"] = 600
    track_b["render"]["bloom_strength"] = 0.34

    return [track_a, gap_track, track_b]


def run_mmd_segment_timing_qa(
    *,
    manifest: str | Path = DEFAULT_MMD_QA_MANIFEST,
    entry_id: str = DEFAULT_MMD_SEGMENT_TIMING_ENTRY_ID,
    out_dir: str | Path = DEFAULT_MMD_SEGMENT_TIMING_QA_OUT_DIR,
    report_path: str | Path = DEFAULT_MMD_SEGMENT_TIMING_QA_REPORT,
    width: int = 360,
    height: int = 202,
    duration_ms: int = 3000,
    fps: int = 12,
) -> dict[str, Any]:
    """Exercise MMD overlay timing through trimmed, gapped, and sped-up export segments."""
    from app.mmd.offscreen_export import MMDOffscreenGLRenderer
    from app.video_exporter import VideoExportThread

    _ensure_qapplication()
    resolved_manifest = resolve_mmd_qa_path(manifest)
    out = Path(out_dir).expanduser().resolve()
    report = Path(report_path).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    width = max(240, int(width or 360))
    height = max(135, int(height or 202))
    duration_ms = max(2600, int(duration_ms or 3000))
    fps = max(4, min(60, int(fps or 12)))

    entry = select_mmd_editor_composite_entry(resolved_manifest, entry_id=entry_id)
    model_path, motion_path = _entry_paths(entry)
    source = out / "mmd_segment_source.mp4"
    baseline = out / "mmd_segment_baseline.mp4"
    final = out / "mmd_segment_export.mp4"
    for path in (source, baseline, final):
        try:
            path.unlink()
        except OSError:
            pass
    _write_synthetic_video(source, width=width, height=height, fps=fps, duration_ms=duration_ms)

    segments = [(100, 900, 1.0), (1300, 2500, 2.0)]
    sample_output_ms = [0, 250, 700, 1000, 1170, 1300]
    tracks = _make_segment_tracks(model_path, motion_path, duration_ms=duration_ms)

    player = ProjectPlayer()
    renderer = MMDOffscreenGLRenderer()
    preview_samples: list[dict[str, Any]] = []
    try:
        player.set_mmd_tracks(tracks)
        for output_ms in sample_output_ms:
            project_ms = _project_ms_for_output_ms(output_ms, segments)
            expected_active = _active_track_ids(tracks, project_ms)
            items = player._mmd_overlay_items(project_ms, animate=True)
            overlay_rgba = renderer.render_array(items, width, height) if items else None
            if overlay_rgba is None:
                overlay_rgba = np.zeros((height, width, 4), dtype=np.uint8)
            overlay_rgba = np.ascontiguousarray(overlay_rgba[:, :, :4], dtype=np.uint8)
            source_probe = _read_video_frame(source, frame_index=_source_frame_index(project_ms, fps))
            if not bool(source_probe.get("ok")):
                raise RuntimeError(f"Could not read MMD segment source frame: {source_probe.get('error')}")
            source_rgb = _strip_rgb_from_probe(source_probe)
            preview_rgb = ProjectPlayer._alpha_composite_rgba_array(source_rgb, overlay_rgba)
            alpha = _alpha_metrics(overlay_rgba)
            active = len(expected_active) > 0
            preview_samples.append(
                {
                    "output_ms": int(output_ms),
                    "project_ms": int(project_ms),
                    "expected_active_track_ids": expected_active,
                    "render_item_track_ids": [str(item.get("track_id") or "") for item in list(items or [])],
                    "alpha_metrics": alpha,
                    "preview_delta": (
                        _composite_delta_metrics(source_rgb, preview_rgb, overlay_rgba)
                        if active
                        else _inactive_delta_metrics(source_rgb, preview_rgb)
                    ),
                    "source_probe": _probe_without_rgb(source_probe),
                    "overlay_rgba": overlay_rgba,
                    "preview_rgb": preview_rgb,
                }
            )
    finally:
        player.release()

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

    sample_reports: list[dict[str, Any]] = []
    for sample in preview_samples:
        output_ms = int(sample["output_ms"])
        frame_index = _sample_frame_index(output_ms, fps)
        baseline_probe = _read_video_frame(baseline, frame_index=frame_index) if baseline.exists() else {"ok": False, "error": "missing_baseline"}
        final_probe = _read_video_frame(final, frame_index=frame_index) if final.exists() else {"ok": False, "error": "missing_final"}
        active = bool(sample["expected_active_track_ids"])
        if bool(baseline_probe.get("ok")) and bool(final_probe.get("ok")):
            baseline_rgb = _strip_rgb_from_probe(baseline_probe)
            final_rgb = _strip_rgb_from_probe(final_probe)
            export_delta = (
                _composite_delta_metrics(baseline_rgb, final_rgb, sample["overlay_rgba"])
                if active
                else _inactive_delta_metrics(baseline_rgb, final_rgb)
            )
            sample_name = f"{output_ms:04d}ms"
            preview_path = _save_rgb(out / f"mmd_segment_preview_{sample_name}.png", sample["preview_rgb"])
            export_path = _save_rgb(out / f"mmd_segment_export_{sample_name}.png", final_rgb)
            overlay_path = _save_rgba(out / f"mmd_segment_overlay_{sample_name}.png", sample["overlay_rgba"])
        else:
            export_delta = {"ok": False, "error": "missing_export_frame"}
            preview_path = ""
            export_path = ""
            overlay_path = ""
        expected_count = len(sample["expected_active_track_ids"])
        render_count = len([value for value in sample["render_item_track_ids"] if value])
        alpha_ok = bool(sample["alpha_metrics"].get("ok")) if active else int(sample["alpha_metrics"].get("alpha_max", 0) or 0) == 0
        sample_ok = (
            render_count == expected_count
            and bool(sample["preview_delta"].get("ok"))
            and bool(export_delta.get("ok"))
            and alpha_ok
        )
        sample_reports.append(
            {
                "ok": bool(sample_ok),
                "output_ms": output_ms,
                "project_ms": int(sample["project_ms"]),
                "expected_active_track_ids": list(sample["expected_active_track_ids"]),
                "render_item_track_ids": list(sample["render_item_track_ids"]),
                "alpha_metrics": sample["alpha_metrics"],
                "preview_delta": sample["preview_delta"],
                "export_delta": export_delta,
                "baseline_probe": _probe_without_rgb(baseline_probe),
                "final_probe": _probe_without_rgb(final_probe),
                "preview_frame": preview_path,
                "export_frame": export_path,
                "overlay_rgba": overlay_path,
            }
        )

    active_counts = [len(row["expected_active_track_ids"]) for row in sample_reports]
    project_ms_samples = [int(row["project_ms"]) for row in sample_reports]
    gap_track_id = "mmd_segment_gap_only"
    gap_track_rendered = any(
        gap_track_id in {str(value) for value in list(row.get("render_item_track_ids") or [])}
        for row in sample_reports
    )
    checks = {
        "track_count_is_three": len(tracks) == 3,
        "segments_include_trim_gap_and_speed": (
            len(segments) == 2
            and int(segments[0][0]) > 0
            and int(segments[0][1]) < int(segments[1][0])
            and any(abs(float(speed) - 1.0) > 0.001 for _start, _end, speed in segments)
        ),
        "mapped_project_ms_match_expected": project_ms_samples == [100, 350, 800, 1700, 2040, 2300],
        "active_counts_match_segment_windows": active_counts == [0, 1, 0, 1, 1, 0],
        "gap_only_track_not_rendered": not gap_track_rendered,
        "mmd_prerender_alpha_mov_created": bool(pre_render.get("ok")) and any(size > 4096 for size in pre_render.get("overlay_sizes", [])),
        "baseline_export_ok": bool(baseline_result.get("ok")) and baseline.exists() and baseline.stat().st_size > 4096,
        "mmd_export_ok": bool(final_result.get("ok")) and final.exists() and final.stat().st_size > 4096,
        "all_segment_samples_ok": all(bool(row.get("ok")) for row in sample_reports),
    }
    failures = [{"check": key, "message": "check failed"} for key, value in checks.items() if not value]
    payload = {
        "ok": not failures,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "kind": "mmd_segment_timing_qa",
        "manifest": str(resolved_manifest),
        "entry_id": str(entry.get("id") or ""),
        "model_path": str(model_path),
        "motion_path": str(motion_path or ""),
        "width": width,
        "height": height,
        "duration_ms": duration_ms,
        "fps": fps,
        "segments": segments,
        "tracks": [
            {
                "id": str(track.get("id") or ""),
                "start_ms": int(track.get("start_ms", 0) or 0),
                "end_ms": int(track.get("end_ms", 0) or 0),
                "motion_start_ms": int((track.get("playback") or {}).get("motion_start_ms", 0) or 0),
                "view": dict(track.get("view") or {}),
            }
            for track in tracks
        ],
        "summary": {
            "checks": len(checks),
            "passing": sum(1 for value in checks.values() if value),
            "failing": len(failures),
            "sample_count": len(sample_reports),
            "active_counts": active_counts,
            "project_ms_samples": project_ms_samples,
            "gap_track_rendered": bool(gap_track_rendered),
            "max_active_export_inside_diff": max(
                [
                    float(row.get("export_delta", {}).get("inside_mean_abs_diff", 0.0) or 0.0)
                    for row in sample_reports
                    if row.get("expected_active_track_ids")
                ]
                or [0.0]
            ),
            "max_inactive_export_mean_diff": max(
                [
                    float(row.get("export_delta", {}).get("mean_abs_diff", 0.0) or 0.0)
                    for row in sample_reports
                    if not row.get("expected_active_track_ids")
                ]
                or [0.0]
            ),
        },
        "checks": checks,
        "pre_render": pre_render,
        "baseline_export": baseline_result,
        "mmd_export": final_result,
        "samples": sample_reports,
        "outputs": {
            "source": str(source),
            "baseline_video": str(baseline),
            "export_video": str(final),
            "out_dir": str(out),
        },
        "failures": failures,
    }
    report.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    payload["report"] = str(report)
    return payload
