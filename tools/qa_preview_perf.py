"""Measure preview-adjacent native worker bottlenecks on the QA corpus.

Run from the repository root:

    .venv\\Scripts\\python.exe tools\\qa_preview_perf.py

The report focuses on two expensive paths that users feel immediately:
batch media probing and timeline thumbnail extraction.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from statistics import mean
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from imageio_ffmpeg import get_ffmpeg_exe


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


PREVIEW_STAGE_NATIVE_ADVICE = {
    "preview.stage.decode": "decode/proxy/hardware frame server",
    "preview.stage.chroma_key": "shader-backed chroma key or native alpha mask",
    "preview.stage.video_filters": "native/GPU filter batch",
    "preview.stage.filter_chroma_batch": "shader/native combined filter+chroma pass",
    "preview.stage.shader_clip_fx_state": "shader clip-effect metadata generation / GL uniform path",
    "preview.stage.spine_overlay": "Spine GPU actor compositor / FBO readback elimination",
    "preview.stage.spine_overlay_state": "Spine direct-GL render-state caching / renderer prewarm",
    "preview.stage.live2d_overlay": "Live2D render cache and startup warm pool",
    "preview.stage.node_effect": "native node-effect worker or GPU node pass",
    "preview.stage.background_removal": "background-removal cache/native worker",
    "preview.stage.qimage": "GPU-only preview consumer / avoid CPU QImage copy",
}

ADVISORY_PREVIEW_STAGE_LABELS = {
    # This is emitted during ProjectPlayer.refresh_tracks(). It is useful for
    # spotting slow project-open/warm-up paths, but it is not a steady preview
    # playback sample and can swing heavily with decoder/process cache state.
    "preview.refresh.render",
}


def _qa_preview_gpu_mode_enabled() -> bool:
    """Default preview perf QA to the main editor's GPU-only preview path."""
    mode = os.environ.get("TIGERCAPTURE_QA_PREVIEW_MODE", "gpu").strip().lower()
    if not mode:
        mode = "gpu"
    return mode not in {"cpu", "qimage", "legacy", "0", "false", "off"}


def _load_manifest(path: Path) -> dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    from tools.build_qa_corpus import build_corpus

    return build_corpus(path.parent)


def _run_quiet(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-1200:])


def _make_hires_video(path: Path, *, size: str, duration: float, fps: int, ffmpeg_path: str) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    _run_quiet([
        ffmpeg_path,
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"testsrc2=size={size}:rate={fps}:duration={duration:.3f}",
        "-t",
        f"{duration:.3f}",
        "-r",
        str(fps),
        "-pix_fmt",
        "yuv420p",
        str(path),
    ])


def _make_preview_proxy(path: Path, *, ffmpeg_path: str, height: int = 540) -> Path | None:
    """Create a fresh sibling proxy that `app.video_decoder` will auto-use."""
    if not path.exists():
        return None
    proxy = path.parent / "proxies" / f"{path.stem}_proxy.mp4"
    try:
        if proxy.is_file() and proxy.stat().st_mtime_ns >= path.stat().st_mtime_ns:
            return proxy
        proxy.parent.mkdir(parents=True, exist_ok=True)
        _run_quiet([
            ffmpeg_path,
            "-y",
            "-i",
            str(path),
            "-vf",
            f"scale=-2:{int(height)}",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "28",
            "-pix_fmt",
            "yuv420p",
            str(proxy),
        ])
        return proxy if proxy.is_file() else None
    except Exception:
        return None


def _write_hires_project(project_path: Path, source: Path, *, name: str, width: int, height: int, duration_ms: int) -> Path:
    project_path.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "version": "1.1",
        "app": "TigerCapture",
        "px_per_sec": 70.0,
        "playhead_ms": 0,
        "global_in_ms": -1,
        "global_out_ms": -1,
        "project_settings": {
            "name": name,
            "canvas_width": width,
            "canvas_height": height,
            "fps": 30.0,
            "ratio_label": "16:9",
            "preview_proxy_recommended": height >= 1080,
        },
        "video_tracks": [{
            "id": 1,
            "source_path": str(source.resolve()),
            "display_name": name,
            "offset_ms": 0,
            "clips": [{
                "id": 1,
                "source_path": str(source.resolve()),
                "source_duration_ms": duration_ms,
                "timeline_in_ms": 0,
                "source_in_ms": 0,
                "source_out_ms": duration_ms,
                "fades": [],
                "zoom_actors": [],
                "typography_actors": [],
                "speed_segments": [],
                "masks": [],
                "node_graph": None,
                "transition_out_type": "",
                "transition_out_ms": 500,
            }],
        }],
        "audio_tracks": [],
        "subtitles": [],
        "media_pool": [str(source.resolve())],
        "spine_actor_tracks": [],
        "live2d_actor_tracks": [],
    }
    project_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return project_path


def _ensure_hires_perf_projects(root: Path, *, ffmpeg_path: str, generate_proxy: bool = False) -> list[Path]:
    assets = root / "preview_perf_assets"
    projects = root / "preview_perf_projects"
    v1080 = assets / "qa_perf_1080p.mp4"
    v4k = assets / "qa_perf_4k.mp4"
    _make_hires_video(v1080, size="1920x1080", duration=2.0, fps=30, ffmpeg_path=ffmpeg_path)
    _make_hires_video(v4k, size="3840x2160", duration=2.0, fps=30, ffmpeg_path=ffmpeg_path)
    if generate_proxy:
        _make_preview_proxy(v1080, ffmpeg_path=ffmpeg_path)
        _make_preview_proxy(v4k, ffmpeg_path=ffmpeg_path)
    return [
        _write_hires_project(
            projects / "06_perf_1080p_baseline.tgp",
            v1080,
            name="QA Perf 1080p Baseline",
            width=1920,
            height=1080,
            duration_ms=2000,
        ),
        _write_hires_project(
            projects / "07_perf_4k_baseline.tgp",
            v4k,
            name="QA Perf 4K Baseline",
            width=3840,
            height=2160,
            duration_ms=2000,
        ),
    ]


def _collect_media(manifest: dict[str, Any]) -> tuple[list[Path], list[Path]]:
    from tools.qa_project_audit import _collect_paths, _load_project

    media: set[Path] = set()
    video: set[Path] = set()
    for raw_project in manifest.get("projects", []) or []:
        project = Path(raw_project)
        if not project.exists():
            continue
        paths = _collect_paths(_load_project(project))
        for raw in paths.get("video", []) or []:
            path = Path(raw)
            if path.exists():
                media.add(path)
                video.add(path)
        for raw in paths.get("audio", []) or []:
            path = Path(raw)
            if path.exists():
                media.add(path)
    return sorted(media), sorted(video)


def _restore_player_tracks(doc: dict[str, Any]) -> tuple[list[Any], list[Any], list[Any]]:
    from app.project_io import (
        _live2d_actor_track_from_dict,
        _spine_actor_track_from_dict,
        _video_clip_from_dict,
    )
    from app.timeline_model import FadeSegment, SpeedSegment, ZoomActor
    from app.typography import TextClip

    tracks: list[Any] = []
    for vt_data in doc.get("video_tracks") or []:
        src_raw = vt_data.get("source_path")
        src_path = Path(src_raw) if src_raw else None
        clips = [
            _video_clip_from_dict(cd, src_path)
            for cd in (vt_data.get("clips") or [])
        ]
        track = SimpleNamespace(
            id=int(vt_data.get("id", len(tracks) + 1)),
            source_path=src_path,
            duration_ms=0,
            offset_ms=int(vt_data.get("offset_ms", 0)),
            cuts=list(vt_data.get("cuts", []) or []),
            clips=clips,
            clips_explicit=True,
            fades=[],
            speed_segments=[],
            zoom_actors=[],
            typography_actors=[],
            pip_enabled=bool(vt_data.get("pip_enabled", False)),
            pip_x=float(vt_data.get("pip_x", 0.5)),
            pip_y=float(vt_data.get("pip_y", 0.5)),
            pip_scale=float(vt_data.get("pip_scale", 0.3)),
            pip_opacity=float(vt_data.get("pip_opacity", 1.0)),
            pip_keyframes=list(vt_data.get("pip_keyframes", []) or []),
            color_grade_chain=None,
            node_mask_chain=None,
            node_item_chain=None,
        )
        for fd in vt_data.get("fades", []) or []:
            try:
                track.fades.append(FadeSegment(int(fd["start_ms"]), int(fd["end_ms"])))
            except Exception:
                pass
        for sd in vt_data.get("speed_segments", []) or []:
            try:
                track.speed_segments.append(SpeedSegment.from_dict(sd))
            except Exception:
                pass
        for zd in vt_data.get("zoom_actors", []) or []:
            try:
                track.zoom_actors.append(ZoomActor(
                    id=int(zd.get("id", 0)),
                    start_ms=int(zd.get("start_ms", 0)),
                    end_ms=int(zd.get("end_ms", 0)),
                    target_x=int(zd.get("target_x", 0)),
                    target_y=int(zd.get("target_y", 0)),
                    target_w=int(zd.get("target_w", 0)),
                    target_h=int(zd.get("target_h", 0)),
                    zoom_in_ms=int(zd.get("zoom_in_ms", 500)),
                    zoom_out_ms=int(zd.get("zoom_out_ms", 500)),
                    easing=str(zd.get("easing", "smooth_pop") or "smooth_pop"),
                    motion_blur=float(zd.get("motion_blur", 0.0) or 0.0),
                ))
            except Exception:
                pass
        for ad in vt_data.get("typography_actors", []) or []:
            try:
                actor = TextClip(
                    start_ms=int(ad.get("start_ms", 0)),
                    end_ms=int(ad.get("end_ms", 0)),
                )
                actor.text = str(ad.get("text", ""))
                track.typography_actors.append(actor)
            except Exception:
                pass
        tracks.append(track)

    spine_tracks: list[Any] = []
    for td in doc.get("spine_actor_tracks") or []:
        try:
            spine_tracks.append(_spine_actor_track_from_dict(td))
        except Exception:
            pass

    live2d_tracks: list[Any] = []
    for td in doc.get("live2d_actor_tracks") or []:
        try:
            live2d_tracks.append(_live2d_actor_track_from_dict(td))
        except Exception:
            pass
    return tracks, spine_tracks, live2d_tracks


def _sample_positions(duration_ms: int, samples: int) -> list[int]:
    duration_ms = max(0, int(duration_ms))
    samples = max(1, int(samples))
    if duration_ms <= 1 or samples == 1:
        return [0]
    end = max(0, duration_ms - 1)
    return sorted({
        int(round(end * i / float(samples - 1)))
        for i in range(samples)
    })


def _clip_feature_positions(doc: dict[str, Any], duration_ms: int) -> list[int]:
    """Project positions that should be sampled even with low sample counts."""
    positions: set[int] = set()
    end_limit = max(0, int(duration_ms) - 1)

    def _add(start_ms: int, duration: int) -> None:
        start = max(0, min(end_limit, int(start_ms)))
        dur = max(0, int(duration))
        if dur <= 0:
            positions.add(start)
            return
        mid = max(0, min(end_limit, start + dur // 2))
        out = max(0, min(end_limit, start + dur - 1))
        positions.update({start, mid, out})

    def _walk_video_clips(clips, base_ms: int = 0) -> None:
        for clip in clips or []:
            start = base_ms + int(clip.get("timeline_in_ms", 0) or 0)
            dur = int(
                clip.get("source_out_ms", 0) or 0
            ) - int(clip.get("source_in_ms", 0) or 0)
            if dur <= 0:
                dur = int(clip.get("source_duration_ms", 0) or 0)
            _add(start, dur)
            for child in clip.get("nested_child_clips") or []:
                _walk_video_clips([child], start)
            for track in clip.get("nested_child_tracks") or []:
                _walk_video_clips(track or [], start)
            for actor_key in ("nested_spine_actor_tracks", "nested_live2d_actor_tracks"):
                for track in clip.get(actor_key) or []:
                    for actor_clip in track.get("clips") or []:
                        _add(
                            start + int(actor_clip.get("start_ms", 0) or 0),
                            int(actor_clip.get("duration_ms", 0) or 0),
                        )

    for vt in doc.get("video_tracks") or []:
        _walk_video_clips(vt.get("clips") or [], 0)
    for actor_key in ("spine_actor_tracks", "live2d_actor_tracks"):
        for track in doc.get(actor_key) or []:
            for actor_clip in track.get("clips") or []:
                _add(
                    int(actor_clip.get("start_ms", 0) or 0),
                    int(actor_clip.get("duration_ms", 0) or 0),
                )
    return sorted(positions)


def _sample_positions_for_project(
    doc: dict[str, Any],
    duration_ms: int,
    samples: int,
) -> list[int]:
    base = set(_sample_positions(duration_ms, samples))
    base.update(_clip_feature_positions(doc, duration_ms))
    return sorted(base)


def _summarize_ms(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "avg_ms": 0.0, "p95_ms": 0.0, "max_ms": 0.0}
    sorted_values = sorted(float(v) for v in values)
    p95_idx = min(len(sorted_values) - 1, int(round((len(sorted_values) - 1) * 0.95)))
    return {
        "count": len(sorted_values),
        "avg_ms": round(mean(sorted_values), 2),
        "p95_ms": round(sorted_values[p95_idx], 2),
        "max_ms": round(sorted_values[-1], 2),
    }


def _summarize_stages(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[float]] = {}
    for row in rows:
        grouped.setdefault(str(row.get("label", "")), []).append(float(row.get("elapsed_ms", 0.0)))
    summary = []
    for label, values in grouped.items():
        stats = _summarize_ms(values)
        stats["label"] = label
        stats["total_ms"] = round(sum(values), 2)
        summary.append(stats)
    return sorted(summary, key=lambda item: (item["total_ms"], item["max_ms"]), reverse=True)


def _summarize_stages_by_context(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        context = str(row.get("context") or "unknown")
        grouped.setdefault(context, []).append(row)
    return {
        context: _summarize_stages(context_rows)
        for context, context_rows in sorted(grouped.items())
    }


def _preview_bottleneck_hints(render_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Translate sampled preview timings into native/GPU migration hints."""
    hints: list[dict[str, Any]] = []
    for row in render_rows:
        project = str(row.get("project", ""))
        by_context = row.get("stage_summary_by_context") or {}
        if isinstance(by_context, dict) and by_context.get("playback"):
            frame_avg = float((row.get("playback_frame_summary") or {}).get("avg_ms", 0.0) or 0.0)
            stages = list(by_context.get("playback") or [])
            hint_context = "playback"
        else:
            frame_avg = float((row.get("frame_summary") or {}).get("avg_ms", 0.0) or 0.0)
            stages = list(row.get("stage_summary") or [])
            hint_context = "mixed"
        slow = [
            s for s in stages
            if str(s.get("label", "")).startswith("preview.stage.")
            and (
                float(s.get("avg_ms", 0.0) or 0.0) >= 8.0
                or float(s.get("p95_ms", 0.0) or 0.0) >= 16.0
            )
        ]
        for stage in slow[:4]:
            label = str(stage.get("label", ""))
            hints.append({
                "project": project,
                "label": label,
                "avg_ms": stage.get("avg_ms", 0.0),
                "p95_ms": stage.get("p95_ms", 0.0),
                "frame_avg_ms": frame_avg,
                "candidate": PREVIEW_STAGE_NATIVE_ADVICE.get(label, "measure before migrating"),
                "context": hint_context,
            })
    return sorted(hints, key=lambda h: (float(h.get("p95_ms", 0.0)), float(h.get("avg_ms", 0.0))), reverse=True)


def _perf_project_key(row: dict[str, Any]) -> str:
    raw = str(row.get("project") or row.get("path") or "")
    if not raw:
        return ""
    try:
        return Path(raw).name
    except Exception:
        return raw


def _preview_rows_by_project(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in report.get("preview_render", []) or []:
        if not isinstance(row, dict):
            continue
        key = _perf_project_key(row)
        if key:
            rows[key] = row
    return rows


def _thumbnail_rows_by_source(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in report.get("timeline_thumbnails", []) or []:
        if not isinstance(row, dict):
            continue
        key = _perf_project_key(row)
        if key:
            rows[key] = row
    return rows


def _stage_rows_by_label(row: dict[str, Any]) -> dict[str, dict[str, Any]]:
    stages: dict[str, dict[str, Any]] = {}
    for stage in row.get("stage_summary", []) or []:
        if not isinstance(stage, dict):
            continue
        label = str(stage.get("label") or "")
        if label:
            stages[label] = stage
    return stages


def _comparison_row(
    *,
    kind: str,
    key: str,
    metric: str,
    current: float,
    baseline: float,
    abs_threshold_ms: float,
    rel_threshold: float,
    label: str = "",
) -> dict[str, Any] | None:
    current = float(current or 0.0)
    baseline = float(baseline or 0.0)
    delta = current - baseline
    if baseline <= 0.0:
        delta_pct = 100.0 if delta > 0 else 0.0
        rel_hit = delta >= abs_threshold_ms
    else:
        delta_pct = (delta / baseline) * 100.0
        rel_hit = abs(delta) / baseline >= rel_threshold
    abs_hit = abs(delta) >= abs_threshold_ms
    if not abs_hit or not rel_hit:
        return None
    row = {
        "kind": kind,
        "key": key,
        "metric": metric,
        "baseline_ms": round(baseline, 2),
        "current_ms": round(current, 2),
        "delta_ms": round(delta, 2),
        "delta_pct": round(delta_pct, 1),
    }
    if label:
        row["label"] = label
        row["candidate"] = PREVIEW_STAGE_NATIVE_ADVICE.get(label, "measure before migrating")
    row["severity"] = "high" if delta >= max(abs_threshold_ms * 2.0, 12.0) else "medium"
    return row


def _append_metric_comparison(
    regressions: list[dict[str, Any]],
    improvements: list[dict[str, Any]],
    *,
    kind: str,
    key: str,
    metric: str,
    current: Any,
    baseline: Any,
    abs_threshold_ms: float,
    rel_threshold: float,
    label: str = "",
) -> None:
    try:
        row = _comparison_row(
            kind=kind,
            key=key,
            metric=metric,
            current=float(current or 0.0),
            baseline=float(baseline or 0.0),
            abs_threshold_ms=abs_threshold_ms,
            rel_threshold=rel_threshold,
            label=label,
        )
    except Exception:
        return
    if not row:
        return
    if float(row["delta_ms"]) > 0:
        regressions.append(row)
    else:
        row["severity"] = "improved"
        improvements.append(row)


def _stage_avg_is_blocking_regression(
    *,
    current_stage: dict[str, Any],
    baseline_stage: dict[str, Any],
    abs_threshold_ms: float,
    rel_threshold: float,
) -> bool:
    row = _comparison_row(
        kind="preview_stage",
        key="",
        metric="avg_ms",
        current=float(current_stage.get("avg_ms", 0.0) or 0.0),
        baseline=float(baseline_stage.get("avg_ms", 0.0) or 0.0),
        abs_threshold_ms=abs_threshold_ms,
        rel_threshold=rel_threshold,
    )
    return bool(row and float(row.get("delta_ms", 0.0) or 0.0) > 0.0)


def _preview_project_sample_plan_changed(
    current_row: dict[str, Any],
    baseline_row: dict[str, Any],
) -> bool:
    try:
        current_count = int(current_row.get("sample_count", 0) or 0)
        baseline_count = int(baseline_row.get("sample_count", 0) or 0)
    except Exception:
        return False
    if current_count <= 0 or baseline_count <= 0 or current_count == baseline_count:
        return False
    ratio = max(current_count, baseline_count) / float(max(1, min(current_count, baseline_count)))
    return ratio >= 1.25


def _advisory_preview_regression_reason(
    row: dict[str, Any],
    *,
    current_projects: dict[str, dict[str, Any]],
    baseline_projects: dict[str, dict[str, Any]],
    abs_threshold_ms: float,
    rel_threshold: float,
) -> str:
    if row.get("kind") != "preview_stage":
        return ""
    label = str(row.get("label") or "")
    if label in ADVISORY_PREVIEW_STAGE_LABELS:
        return "warmup_or_project_refresh_sample"
    key = str(row.get("key") or "")
    current_project = current_projects.get(key, {}) or {}
    baseline_project = baseline_projects.get(key, {}) or {}
    if _preview_project_sample_plan_changed(current_project, baseline_project):
        return "sample_plan_changed_stage_not_directly_comparable"
    if row.get("metric") != "p95_ms":
        return ""

    current_stage = _stage_rows_by_label(current_project).get(label, {})
    baseline_stage = _stage_rows_by_label(baseline_project).get(label, {})
    if not current_stage or not baseline_stage:
        return ""
    if _stage_avg_is_blocking_regression(
        current_stage=current_stage,
        baseline_stage=baseline_stage,
        abs_threshold_ms=abs_threshold_ms,
        rel_threshold=rel_threshold,
    ):
        return ""
    return "p95_stage_spike_without_sustained_avg_regression"


def compare_preview_perf_reports(
    current: dict[str, Any],
    baseline: dict[str, Any],
    *,
    abs_threshold_ms: float = 5.0,
    rel_threshold: float = 0.25,
) -> dict[str, Any]:
    """Compare two preview perf reports and flag meaningful regressions."""
    regressions: list[dict[str, Any]] = []
    improvements: list[dict[str, Any]] = []

    _append_metric_comparison(
        regressions,
        improvements,
        kind="media_probe",
        key="batch",
        metric="elapsed_ms",
        current=current.get("batch_media_probe_elapsed_ms", 0.0),
        baseline=baseline.get("batch_media_probe_elapsed_ms", 0.0),
        abs_threshold_ms=abs_threshold_ms,
        rel_threshold=rel_threshold,
    )

    current_thumbs = _thumbnail_rows_by_source(current)
    baseline_thumbs = _thumbnail_rows_by_source(baseline)
    for key in sorted(set(current_thumbs) & set(baseline_thumbs)):
        _append_metric_comparison(
            regressions,
            improvements,
            kind="timeline_thumbnail",
            key=key,
            metric="elapsed_ms",
            current=current_thumbs[key].get("elapsed_ms", 0.0),
            baseline=baseline_thumbs[key].get("elapsed_ms", 0.0),
            abs_threshold_ms=abs_threshold_ms,
            rel_threshold=rel_threshold,
        )

    current_projects = _preview_rows_by_project(current)
    baseline_projects = _preview_rows_by_project(baseline)
    for key in sorted(set(current_projects) & set(baseline_projects)):
        current_row = current_projects[key]
        baseline_row = baseline_projects[key]
        current_frame = current_row.get("frame_summary", {}) or {}
        baseline_frame = baseline_row.get("frame_summary", {}) or {}
        for metric in ("avg_ms", "p95_ms", "max_ms"):
            _append_metric_comparison(
                regressions,
                improvements,
                kind="preview_frame",
                key=key,
                metric=metric,
                current=current_frame.get(metric, 0.0),
                baseline=baseline_frame.get(metric, 0.0),
                abs_threshold_ms=abs_threshold_ms,
                rel_threshold=rel_threshold,
            )
        current_stages = _stage_rows_by_label(current_row)
        baseline_stages = _stage_rows_by_label(baseline_row)
        for label in sorted(set(current_stages) & set(baseline_stages)):
            for metric in ("avg_ms", "p95_ms"):
                _append_metric_comparison(
                    regressions,
                    improvements,
                    kind="preview_stage",
                    key=key,
                    label=label,
                    metric=metric,
                    current=current_stages[label].get(metric, 0.0),
                    baseline=baseline_stages[label].get(metric, 0.0),
                    abs_threshold_ms=abs_threshold_ms,
                    rel_threshold=rel_threshold,
                )

    blocking_regressions: list[dict[str, Any]] = []
    advisory_regressions: list[dict[str, Any]] = []
    for row in regressions:
        reason = _advisory_preview_regression_reason(
            row,
            current_projects=current_projects,
            baseline_projects=baseline_projects,
            abs_threshold_ms=abs_threshold_ms,
            rel_threshold=rel_threshold,
        )
        if reason:
            advisory = dict(row)
            advisory["advisory_reason"] = reason
            advisory_regressions.append(advisory)
        else:
            blocking_regressions.append(row)

    blocking_regressions.sort(key=lambda row: (float(row["delta_ms"]), abs(float(row["delta_pct"]))), reverse=True)
    advisory_regressions.sort(key=lambda row: (float(row["delta_ms"]), abs(float(row["delta_pct"]))), reverse=True)
    improvements.sort(key=lambda row: (abs(float(row["delta_ms"])), abs(float(row["delta_pct"]))), reverse=True)
    new_projects = sorted(set(current_projects) - set(baseline_projects))
    missing_projects = sorted(set(baseline_projects) - set(current_projects))
    return {
        "ok": not blocking_regressions,
        "thresholds": {
            "abs_threshold_ms": float(abs_threshold_ms),
            "rel_threshold": float(rel_threshold),
        },
        "summary": {
            "regressions": len(blocking_regressions),
            "advisory_regressions": len(advisory_regressions),
            "total_regression_signals": len(blocking_regressions) + len(advisory_regressions),
            "improvements": len(improvements),
            "new_projects": len(new_projects),
            "missing_projects": len(missing_projects),
        },
        "regressions": blocking_regressions,
        "advisory_regressions": advisory_regressions,
        "improvements": improvements,
        "new_projects": new_projects,
        "missing_projects": missing_projects,
    }


def _measure_preview_render(project_path: Path, *, samples: int) -> dict[str, Any]:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ["TIGERCAPTURE_PERF"] = "1"

    from PySide6.QtWidgets import QApplication
    from app import perf_monitor
    from app.preview_acceleration import configure_preview_acceleration_defaults
    from app.project_player import ProjectPlayer
    from tools.qa_project_audit import _load_project, _summarize

    acceleration_defaults = configure_preview_acceleration_defaults()
    _app = QApplication.instance() or QApplication([])
    _ = _app
    doc = _load_project(project_path)
    tracks, spine_tracks, live2d_tracks = _restore_player_tracks(doc)

    stage_rows: list[dict[str, Any]] = []
    old_log_perf = perf_monitor.log_perf
    perf_context = {"value": "setup"}

    def _capture_perf(label: str, elapsed_ms: float, *, detail: str = "", threshold_ms=None) -> None:
        stage_rows.append({
            "label": label,
            "elapsed_ms": round(float(elapsed_ms), 3),
            "detail": detail,
            "context": perf_context["value"],
        })

    perf_monitor.log_perf = _capture_perf
    player = ProjectPlayer()
    qa_gpu_mode = _qa_preview_gpu_mode_enabled()
    if qa_gpu_mode:
        player.set_qimage_frame_enabled(False)
    qimage_enabled = bool(player.qimage_frame_enabled())
    errors: list[str] = []
    player.error_occurred.connect(lambda msg: errors.append(str(msg)))
    try:
        start = time.perf_counter()
        perf_context["value"] = "refresh"
        player.refresh_tracks(tracks, render_immediately=False)
        perf_context["value"] = "actor_setup"
        player.set_spine_actor_tracks(spine_tracks)
        player.set_live2d_actor_tracks(live2d_tracks)
        setup_elapsed_ms = round((time.perf_counter() - start) * 1000.0, 2)
        duration_ms = int(player.duration())
        positions = _sample_positions_for_project(doc, duration_ms, samples)
        frame_rows: list[dict[str, Any]] = []
        for pos in positions:
            start = time.perf_counter()
            perf_context["value"] = "seek"
            player.set_position(pos)
            elapsed_ms = round((time.perf_counter() - start) * 1000.0, 2)
            frame_rows.append({"pos_ms": int(pos), "elapsed_ms": elapsed_ms})
        playback_rows: list[dict[str, Any]] = []
        if duration_ms > 33:
            perf_context["value"] = "playback_warmup"
            player.set_position(0)
            playback_samples = max(4, min(18, int(samples) * 3))
            for _idx in range(playback_samples):
                if int(player.position()) >= max(0, duration_ms - 34):
                    break
                start = time.perf_counter()
                perf_context["value"] = "playback"
                player._tick()
                elapsed_ms = round((time.perf_counter() - start) * 1000.0, 2)
                playback_rows.append({
                    "pos_ms": int(player.position()),
                    "elapsed_ms": elapsed_ms,
                })
        qimage_enabled = bool(player.qimage_frame_enabled())
    finally:
        player.release()
        perf_monitor.log_perf = old_log_perf

    frame_values = [float(row["elapsed_ms"]) for row in frame_rows]
    playback_values = [float(row["elapsed_ms"]) for row in playback_rows]
    return {
        "project": str(project_path),
        "summary": _summarize(doc),
        "setup_elapsed_ms": setup_elapsed_ms,
        "duration_ms": duration_ms,
        "sample_count": len(frame_rows),
        "preview_mode": {
            "qa_gpu_mode": bool(qa_gpu_mode),
            "qimage_enabled": bool(qimage_enabled),
            "acceleration_defaults": acceleration_defaults,
        },
        "frames": frame_rows,
        "frame_summary": _summarize_ms(frame_values),
        "playback_frames": playback_rows,
        "playback_frame_summary": _summarize_ms(playback_values),
        "stage_summary": _summarize_stages(stage_rows),
        "stage_summary_by_context": _summarize_stages_by_context(stage_rows),
        "stage_samples": stage_rows[:200],
        "errors": errors,
        "ok": not errors and bool(frame_rows),
    }


def run_perf(
    manifest_path: Path,
    out: Path,
    *,
    clean: bool = False,
    render_samples: int = 8,
    skip_render: bool = False,
    include_hires: bool = False,
    include_hires_proxy: bool = False,
    baseline_report: dict[str, Any] | None = None,
    baseline_abs_threshold_ms: float = 5.0,
    baseline_rel_threshold: float = 0.25,
) -> dict[str, Any]:
    from app.native_worker import (
        get_native_worker_capabilities,
        native_generate_timeline_thumbnails,
        native_media_probe_many,
    )

    manifest = _load_manifest(manifest_path)
    media_paths, video_paths = _collect_media(manifest)
    ffmpeg_path = get_ffmpeg_exe()
    thumb_root = out.parent / "preview_perf_thumbs"
    if clean and thumb_root.exists():
        shutil.rmtree(thumb_root)
    thumb_root.mkdir(parents=True, exist_ok=True)

    capabilities = get_native_worker_capabilities()
    cap_dict = capabilities.__dict__ if capabilities is not None else None

    start = time.perf_counter()
    probes = native_media_probe_many(media_paths, ffmpeg_path=ffmpeg_path)
    batch_elapsed_ms = round((time.perf_counter() - start) * 1000.0, 2)

    probe_rows: list[dict[str, Any]] = []
    for path, probe in zip(media_paths, probes or []):
        probe_rows.append({
            "path": str(path),
            "ok": probe is not None,
            "duration_ms": getattr(probe, "duration_ms", None),
            "width": getattr(probe, "width", None),
            "height": getattr(probe, "height", None),
            "fps": getattr(probe, "fps", None),
        })

    thumb_rows: list[dict[str, Any]] = []
    for idx, path in enumerate(video_paths):
        target = thumb_root / f"{idx:02d}_{path.stem}"
        start = time.perf_counter()
        files = native_generate_timeline_thumbnails(
            path,
            target,
            ffmpeg_path=ffmpeg_path,
            thumb_h=56,
            min_thumbs=8,
            max_thumbs=16,
            seconds_per_tile=2.0,
        )
        elapsed_ms = round((time.perf_counter() - start) * 1000.0, 2)
        thumb_rows.append({
            "path": str(path),
            "ok": bool(files),
            "thumbnail_count": len(files or []),
            "elapsed_ms": elapsed_ms,
            "out_dir": str(target),
        })

    render_rows: list[dict[str, Any]] = []
    if not skip_render:
        project_paths = [Path(raw) for raw in manifest.get("projects", []) or []]
        if include_hires:
            project_paths.extend(
                _ensure_hires_perf_projects(
                    out.parent,
                    ffmpeg_path=ffmpeg_path,
                    generate_proxy=bool(include_hires_proxy),
                )
            )
        for project in project_paths:
            if not project.exists():
                continue
            render_rows.append(_measure_preview_render(project, samples=render_samples))

    report = {
        "ok": (
            bool(probes is not None)
            and all(row["ok"] for row in thumb_rows)
            and (skip_render or all(row.get("ok", False) for row in render_rows))
        ),
        "manifest": str(manifest_path),
        "native_capabilities": cap_dict,
        "media_count": len(media_paths),
        "video_count": len(video_paths),
        "batch_media_probe_elapsed_ms": batch_elapsed_ms,
        "media_probe": probe_rows,
        "timeline_thumbnails": thumb_rows,
        "preview_render": render_rows,
    }
    try:
        from app.preview_engine_status import preview_engine_status
        report["preview_engine"] = preview_engine_status()
    except Exception:
        report["preview_engine"] = {}
    report["native_gpu_candidates"] = _preview_bottleneck_hints(render_rows)
    if baseline_report:
        comparison = compare_preview_perf_reports(
            report,
            baseline_report,
            abs_threshold_ms=baseline_abs_threshold_ms,
            rel_threshold=baseline_rel_threshold,
        )
        report["baseline_comparison"] = comparison
        report["ok"] = bool(report.get("ok", False) and comparison.get("ok", False))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("qa_corpus/qa_corpus_manifest.json"))
    parser.add_argument("--out", type=Path, default=Path("debugCapture/preview_perf_report.json"))
    parser.add_argument("--clean", action="store_true", help="Clear previous thumbnail benchmark output first.")
    parser.add_argument("--render-samples", type=int, default=8, help="Preview frames to render per project.")
    parser.add_argument("--skip-render", action="store_true", help="Only measure media probe and thumbnail paths.")
    parser.add_argument("--include-hires", action="store_true", help="Also generate and measure 1080p/4K preview fixtures.")
    parser.add_argument("--include-hires-proxy", action="store_true", help="Generate fresh 540p sibling proxies for the 1080p/4K fixtures before measuring.")
    parser.add_argument("--baseline", type=Path, help="Previous qa_preview_perf JSON report to compare against.")
    parser.add_argument("--baseline-abs-ms", type=float, default=5.0, help="Minimum absolute ms delta for regression/improvement.")
    parser.add_argument("--baseline-rel", type=float, default=0.25, help="Minimum relative delta for regression/improvement.")
    args = parser.parse_args()
    baseline_report = None
    if args.baseline and args.baseline.exists():
        baseline_report = json.loads(args.baseline.read_text(encoding="utf-8"))
    report = run_perf(
        args.manifest,
        args.out,
        clean=args.clean,
        render_samples=args.render_samples,
        skip_render=args.skip_render,
        include_hires=args.include_hires,
        include_hires_proxy=args.include_hires_proxy,
        baseline_report=baseline_report,
        baseline_abs_threshold_ms=args.baseline_abs_ms,
        baseline_rel_threshold=args.baseline_rel,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"report: {args.out}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
