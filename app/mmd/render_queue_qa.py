"""Render-queue wiring QA for MMD actor export."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from app.mmd.editor_composite_qa import (
    DEFAULT_MMD_EDITOR_COMPOSITE_ENTRY_ID,
    _alpha_metrics,
    _composite_delta_metrics,
    _entry_paths,
    _ensure_qapplication,
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
    _project_ms_for_output_ms,
    _sample_frame_index,
    _strip_rgb_from_probe,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MMD_RENDER_QUEUE_QA_OUT_DIR = ROOT / "debugCapture" / "mmd_player" / "render_queue_qa"
DEFAULT_MMD_RENDER_QUEUE_QA_REPORT = ROOT / "debugCapture" / "mmd_player" / "mmd_render_queue_qa.json"
DEFAULT_MMD_RENDER_QUEUE_EXPORT_QA_REPORT = ROOT / "debugCapture" / "mmd_player" / "mmd_render_queue_export_qa.json"
DEFAULT_MMD_LONG_PROJECT_EXPORT_QA_REPORT = ROOT / "debugCapture" / "mmd_player" / "mmd_long_project_export_qa.json"
DEFAULT_MMD_RENDER_QUEUE_ENTRY_ID = DEFAULT_MMD_EDITOR_COMPOSITE_ENTRY_ID


class _SignalProbe:
    def __init__(self) -> None:
        self.callbacks: list[Any] = []

    def connect(self, callback: Any) -> None:
        self.callbacks.append(callback)


class _FakeRenderQueuePanel:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def queue_items(self, items: list[Any], export_fn: Any, **kwargs: Any) -> list[str]:
        job_ids = [f"mmd_render_queue_job_{idx + 1:03d}" for idx, _item in enumerate(items)]
        self.calls.append(
            {
                "items": list(items),
                "export_fn": export_fn,
                "kwargs": dict(kwargs),
                "job_ids": job_ids,
            }
        )
        return job_ids


def _make_render_queue_mmd_tracks(
    model_path: Path,
    motion_path: Path | None,
    *,
    count: int,
    start_ms: int = 500,
    end_ms: int = 1500,
    prefix: str = "mmd_render_queue",
) -> list[dict[str, Any]]:
    count = max(0, int(count))
    if count <= 0:
        return []
    offsets = [0.0] if count == 1 else [-0.24, 0.24]
    tracks: list[dict[str, Any]] = []
    start = max(0, int(start_ms))
    end = max(start + 1, int(end_ms))
    for index in range(count):
        track = create_preview_mmd_track(
            model_path,
            track_id=f"{prefix}_{index + 1:03d}",
            start_ms=start,
            duration_ms=end - start,
            motion_path=motion_path,
        )
        track["end_ms"] = end
        track["duration_ms"] = end - start
        track["view"].update(
            {
                "offset_x": offsets[index] if index < len(offsets) else 0.0,
                "offset_y": 0.02,
                "zoom": 0.58 if count > 1 else 0.72,
            }
        )
        track["playback"]["motion_start_ms"] = 350 * index
        track["render"]["bloom_strength"] = 0.24 + 0.08 * index
        tracks.append(track)
    return tracks


def _fake_editor(
    *,
    source_path: Path,
    out_dir: Path,
    model_path: Path,
    motion_path: Path | None,
    with_mmd: bool = True,
    mmd_track_count: int = 1,
    source_duration_ms: int = 2400,
    timeline_markers: list[dict[str, Any]] | None = None,
    speed_segments: list[tuple[int, int, float]] | None = None,
    mmd_tracks_override: list[dict[str, Any]] | None = None,
    export_resolution: tuple[int, int] = (640, 360),
    export_fps: int = 24,
) -> Any:
    from app.timeline_model import SpeedSegment, VideoClip
    from app.video_editor_window import VideoEditorWindow

    editor = VideoEditorWindow.__new__(VideoEditorWindow)
    duration = max(1, int(source_duration_ms or 2400))
    clip = VideoClip(
        id=1,
        source_path=source_path,
        source_duration_ms=duration,
        timeline_in_ms=0,
        source_in_ms=0,
        source_out_ms=duration,
    )
    track = SimpleNamespace(
        source_path=source_path,
        clips=[clip],
        speed_segments=[
            SpeedSegment(int(start), int(end), float(speed))
            for start, end, speed in (speed_segments if speed_segments is not None else [(900, 1500, 2.0)])
        ],
        cuts=[],
        fades=[],
        color_grade=None,
    )
    player = SimpleNamespace(
        duration=lambda: duration,
        _ar_pbr_asset_descriptor_cache={},
    )
    if mmd_tracks_override is not None:
        mmd_tracks = list(mmd_tracks_override) if with_mmd else []
    else:
        mmd_tracks = _make_render_queue_mmd_tracks(
            model_path,
            motion_path,
            count=mmd_track_count if with_mmd else 0,
        )

    editor._active_track = lambda: track
    editor._timeline_markers = list(
        timeline_markers
        if timeline_markers is not None
        else [
            {"ms": 500, "label": "MMD Segment"},
            {"ms": 1500, "label": "End"},
        ]
    )
    editor._player = player
    editor._export_format_id = "mp4"
    editor._export_quality_id = "low"
    editor._export_fps = max(1, int(export_fps or 24))
    editor._export_resolution = (max(1, int(export_resolution[0])), max(1, int(export_resolution[1])))
    editor._project_settings = {}
    editor._project_path = str(out_dir / "mmd_render_queue_project.tcp")
    editor._mmd_tracks = mmd_tracks
    editor._spine_actor_tracks = []
    editor._live2d_actor_tracks = []
    editor._ar_pbr_tracks = []
    editor._audio_tracks = []
    editor._strokes = []
    editor._bubbles = []
    editor._stickers = []
    editor._subtitle_panel = SimpleNamespace(subtitles=lambda: [])
    editor._render_queue_panel = _FakeRenderQueuePanel()
    editor._rebuild_active_chain = lambda: None
    editor._show_export_final_checklist = lambda _note, job_count=1: True
    editor._color_audio_export_badge_note = lambda: ""
    editor._audio_delivery_export_note = lambda: ""
    editor._snapshot_node_item_chain_for_export = lambda _track: []
    editor._snapshot_clip_effects_for_export = lambda _track: []
    editor._export_zoom_actors_for_track = lambda _track: []
    editor._flash_messages = []
    editor._flash_status = lambda text: editor._flash_messages.append(str(text))
    return editor


def _capture_batch_export_call(editor: Any, out: Path) -> dict[str, Any]:
    import app.video_editor_window as video_editor_window

    class FakeFileDialog:
        @staticmethod
        def getExistingDirectory(*_args: Any, **_kwargs: Any) -> str:
            return str(out)

    class FakeMessageBox:
        @staticmethod
        def warning(*_args: Any, **_kwargs: Any) -> None:
            return None

        @staticmethod
        def information(*_args: Any, **_kwargs: Any) -> None:
            return None

    previous_file_dialog = video_editor_window.QFileDialog
    previous_message_box = video_editor_window.QMessageBox
    try:
        video_editor_window.QFileDialog = FakeFileDialog
        video_editor_window.QMessageBox = FakeMessageBox
        video_editor_window.VideoEditorWindow._on_batch_export(editor)
    finally:
        video_editor_window.QFileDialog = previous_file_dialog
        video_editor_window.QMessageBox = previous_message_box
    return editor._render_queue_panel.calls[0] if editor._render_queue_panel.calls else {}


def run_mmd_render_queue_wiring_qa(
    *,
    manifest: str | Path = DEFAULT_MMD_QA_MANIFEST,
    entry_id: str = DEFAULT_MMD_RENDER_QUEUE_ENTRY_ID,
    out_dir: str | Path = DEFAULT_MMD_RENDER_QUEUE_QA_OUT_DIR,
    report_path: str | Path = DEFAULT_MMD_RENDER_QUEUE_QA_REPORT,
) -> dict[str, Any]:
    """Verify batch/render-queue export forwards MMD pre-render overlays."""
    import app.video_editor_window as video_editor_window
    import app.video_exporter as video_exporter

    resolved_manifest = resolve_mmd_qa_path(manifest)
    out = Path(out_dir).expanduser().resolve()
    report = Path(report_path).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)

    entry = select_mmd_editor_composite_entry(resolved_manifest, entry_id=entry_id)
    model_path, motion_path = _entry_paths(entry)
    source = out / "mmd_render_queue_source.mp4"
    source.write_bytes(b"mmd render queue qa placeholder")

    pre_render_calls: list[dict[str, Any]] = []
    thread_inits: list[dict[str, Any]] = []
    progress_values: list[int] = []
    overlay_spec = [(str(out / "mmd_render_queue_alpha.mov"), 0.0, 0.75)]

    class FakeVideoExportThread:
        @staticmethod
        def pre_render_mmd_actors(**kwargs: Any) -> list[tuple[str, float, float]]:
            pre_render_calls.append(dict(kwargs))
            progress_cb = kwargs.get("progress_cb")
            if callable(progress_cb):
                progress_cb(80)
            return list(overlay_spec)

        def __init__(self, source_path: Any, out_path: Any, segments: Any, *args: Any, **kwargs: Any) -> None:
            self.progress = _SignalProbe()
            self.finished_error = _SignalProbe()
            self.finished_success = _SignalProbe()
            self.stage = _SignalProbe()
            self.finished = _SignalProbe()
            thread_inits.append(
                {
                    "source_path": str(source_path),
                    "out_path": str(out_path),
                    "segments": list(segments or []),
                    "kwargs": dict(kwargs),
                }
            )

    class FakeFileDialog:
        @staticmethod
        def getExistingDirectory(*_args: Any, **_kwargs: Any) -> str:
            return str(out)

    class FakeMessageBox:
        @staticmethod
        def warning(*_args: Any, **_kwargs: Any) -> None:
            return None

        @staticmethod
        def information(*_args: Any, **_kwargs: Any) -> None:
            return None

    previous_thread = video_exporter.VideoExportThread
    previous_file_dialog = video_editor_window.QFileDialog
    previous_message_box = video_editor_window.QMessageBox
    editor = _fake_editor(
        source_path=source,
        out_dir=out,
        model_path=model_path,
        motion_path=motion_path,
    )
    try:
        video_exporter.VideoExportThread = FakeVideoExportThread
        video_editor_window.QFileDialog = FakeFileDialog
        video_editor_window.QMessageBox = FakeMessageBox
        video_editor_window.VideoEditorWindow._on_batch_export(editor)
        panel = editor._render_queue_panel
        queued_call = panel.calls[0] if panel.calls else {}
        items = list(queued_call.get("items") or [])
        export_fn = queued_call.get("export_fn")
        if callable(export_fn) and items:
            item = items[0]
            export_fn(
                int(getattr(item, "in_ms", 0) or 0),
                int(getattr(item, "out_ms", 0) or 0),
                str(getattr(item, "out_path", out / "mmd_render_queue_out.mp4")),
                progress_cb=lambda value: progress_values.append(int(value)),
            )
    finally:
        video_exporter.VideoExportThread = previous_thread
        video_editor_window.QFileDialog = previous_file_dialog
        video_editor_window.QMessageBox = previous_message_box

    queued_call = editor._render_queue_panel.calls[0] if editor._render_queue_panel.calls else {}
    queued_items = list(queued_call.get("items") or [])
    pre_render = pre_render_calls[0] if pre_render_calls else {}
    thread_init = thread_inits[0] if thread_inits else {}
    expected_segments = [(500, 900, 1.0), (900, 1500, 2.0)]
    checks = {
        "render_queue_job_queued": len(queued_items) == 1,
        "queue_auto_start_requested": bool((queued_call.get("kwargs") or {}).get("auto_start")),
        "pre_render_called_for_mmd_tracks": bool(pre_render_calls),
        "pre_render_segments_match_trimmed_speed_range": list(pre_render.get("segments") or []) == expected_segments,
        "pre_render_uses_export_resolution": tuple(pre_render.get("frame_size") or ()) == (640, 360),
        "pre_render_progress_scaled_before_encoder": progress_values == [28],
        "thread_created": bool(thread_inits),
        "thread_segments_match_pre_render_segments": list(thread_init.get("segments") or []) == expected_segments,
        "thread_receives_mmd_tracks": list((thread_init.get("kwargs") or {}).get("mmd_tracks") or []) == list(editor._mmd_tracks),
        "thread_receives_mmd_pre_rendered_overlay": list((thread_init.get("kwargs") or {}).get("mmd_pre_rendered") or []) == overlay_spec,
    }
    failures = [{"check": key, "message": "check failed"} for key, value in checks.items() if not value]
    payload = {
        "ok": not failures,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "kind": "mmd_render_queue_wiring_qa",
        "manifest": str(resolved_manifest),
        "entry_id": str(entry.get("id") or ""),
        "model_path": str(model_path),
        "motion_path": str(motion_path or ""),
        "summary": {
            "checks": len(checks),
            "passing": sum(1 for value in checks.values() if value),
            "failing": len(failures),
            "queued_jobs": len(queued_items),
            "pre_render_calls": len(pre_render_calls),
            "thread_inits": len(thread_inits),
            "progress_values": list(progress_values),
            "segments": expected_segments,
        },
        "checks": checks,
        "queue_call": {
            "job_ids": list(queued_call.get("job_ids") or []),
            "kwargs": dict(queued_call.get("kwargs") or {}),
            "items": [
                {
                    "label": str(getattr(item, "label", "") or ""),
                    "out_path": str(getattr(item, "out_path", "") or ""),
                    "in_ms": int(getattr(item, "in_ms", 0) or 0),
                    "out_ms": int(getattr(item, "out_ms", 0) or 0),
                }
                for item in queued_items
            ],
        },
        "pre_render_call": {
            "tracks": [str(track.get("id") or "") for track in list(pre_render.get("tracks") or [])],
            "source_path": str(pre_render.get("source_path") or ""),
            "fps": int(pre_render.get("fps", 0) or 0),
            "segments": list(pre_render.get("segments") or []),
            "frame_size": list(pre_render.get("frame_size") or []),
        },
        "thread_init": {
            "source_path": str(thread_init.get("source_path") or ""),
            "out_path": str(thread_init.get("out_path") or ""),
            "segments": list(thread_init.get("segments") or []),
            "mmd_track_ids": [
                str(track.get("id") or "")
                for track in list((thread_init.get("kwargs") or {}).get("mmd_tracks") or [])
            ],
            "mmd_pre_rendered": list((thread_init.get("kwargs") or {}).get("mmd_pre_rendered") or []),
        },
        "outputs": {
            "out_dir": str(out),
            "source": str(source),
        },
        "failures": failures,
    }
    report.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    payload["report"] = str(report)
    return payload


def run_mmd_render_queue_export_qa(
    *,
    manifest: str | Path = DEFAULT_MMD_QA_MANIFEST,
    entry_id: str = DEFAULT_MMD_RENDER_QUEUE_ENTRY_ID,
    out_dir: str | Path = DEFAULT_MMD_RENDER_QUEUE_QA_OUT_DIR,
    report_path: str | Path = DEFAULT_MMD_RENDER_QUEUE_EXPORT_QA_REPORT,
    width: int = 640,
    height: int = 360,
    duration_ms: int = 2400,
    fps: int = 24,
) -> dict[str, Any]:
    """Run the batch/render-queue export factory and verify the output MP4 contains MMD pixels."""
    from app.mmd.offscreen_export import MMDOffscreenGLRenderer
    from app.project_player import ProjectPlayer

    _ensure_qapplication()
    resolved_manifest = resolve_mmd_qa_path(manifest)
    out = Path(out_dir).expanduser().resolve()
    report = Path(report_path).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    width = max(320, int(width or 640))
    height = max(180, int(height or 360))
    duration_ms = max(1800, int(duration_ms or 2400))
    fps = max(8, min(60, int(fps or 24)))

    entry = select_mmd_editor_composite_entry(resolved_manifest, entry_id=entry_id)
    model_path, motion_path = _entry_paths(entry)
    source = out / "mmd_render_queue_export_source.mp4"
    baseline = out / "mmd_render_queue_baseline.mp4"
    final = out / "mmd_render_queue_export.mp4"
    for path in (source, baseline, final):
        try:
            path.unlink()
        except OSError:
            pass
    _write_synthetic_video(source, width=width, height=height, fps=fps, duration_ms=duration_ms)

    editor_with_mmd = _fake_editor(
        source_path=source,
        out_dir=out,
        model_path=model_path,
        motion_path=motion_path,
        with_mmd=True,
        mmd_track_count=2,
    )
    editor_without_mmd = _fake_editor(
        source_path=source,
        out_dir=out,
        model_path=model_path,
        motion_path=motion_path,
        with_mmd=False,
    )
    final_call = _capture_batch_export_call(editor_with_mmd, out)
    baseline_call = _capture_batch_export_call(editor_without_mmd, out)
    final_items = list(final_call.get("items") or [])
    baseline_items = list(baseline_call.get("items") or [])
    final_export_fn = final_call.get("export_fn")
    baseline_export_fn = baseline_call.get("export_fn")
    final_result: dict[str, Any] = {"ok": False, "error": "missing_export_fn"}
    baseline_result: dict[str, Any] = {"ok": False, "error": "missing_export_fn"}
    final_pre_rendered: list[Any] = []
    final_pre_render_sizes: list[int] = []
    progress_values: list[int] = []
    expected_segments = [(500, 900, 1.0), (900, 1500, 2.0)]

    if callable(baseline_export_fn) and baseline_items:
        item = baseline_items[0]
        baseline_thread = baseline_export_fn(
            int(getattr(item, "in_ms", 0) or 0),
            int(getattr(item, "out_ms", 0) or 0),
            str(baseline),
            progress_cb=None,
        )
        baseline_result = _run_export(baseline_thread)
    if callable(final_export_fn) and final_items:
        item = final_items[0]
        final_thread = final_export_fn(
            int(getattr(item, "in_ms", 0) or 0),
            int(getattr(item, "out_ms", 0) or 0),
            str(final),
            progress_cb=lambda value: progress_values.append(int(value)),
        )
        final_pre_rendered = list(getattr(final_thread, "_mmd_pre_rendered", []) or [])
        final_pre_render_sizes = [
            int(Path(path).stat().st_size) if Path(path).exists() else 0
            for path, _start, _end in final_pre_rendered
        ]
        final_result = _run_export(final_thread)

    sample_output_ms = 100
    sample_project_ms = _project_ms_for_output_ms(sample_output_ms, expected_segments)
    sample_frame_index = _sample_frame_index(sample_output_ms, fps)

    overlay_rgba = None
    render_item_track_ids: list[str] = []
    player = ProjectPlayer()
    renderer = MMDOffscreenGLRenderer()
    try:
        player.set_mmd_tracks(list(getattr(editor_with_mmd, "_mmd_tracks", []) or []))
        items = player._mmd_overlay_items(sample_project_ms, animate=True)
        render_item_track_ids = [str(item.get("track_id") or "") for item in list(items or [])]
        overlay_rgba = renderer.render_array(items, width, height) if items else None
    finally:
        player.release()
    if overlay_rgba is None:
        import numpy as np

        overlay_rgba = np.zeros((height, width, 4), dtype=np.uint8)
    import numpy as np

    overlay_rgba = np.ascontiguousarray(overlay_rgba[:, :, :4], dtype=np.uint8)
    alpha = _alpha_metrics(overlay_rgba)

    baseline_probe = _read_video_frame(baseline, frame_index=sample_frame_index) if baseline.exists() else {"ok": False, "error": "missing_baseline"}
    final_probe = _read_video_frame(final, frame_index=sample_frame_index) if final.exists() else {"ok": False, "error": "missing_final"}
    if bool(baseline_probe.get("ok")) and bool(final_probe.get("ok")):
        baseline_rgb = _strip_rgb_from_probe(baseline_probe)
        final_rgb = _strip_rgb_from_probe(final_probe)
        export_delta = _composite_delta_metrics(baseline_rgb, final_rgb, overlay_rgba)
        baseline_frame = _save_rgb(out / "mmd_render_queue_baseline_frame.png", baseline_rgb)
        export_frame = _save_rgb(out / "mmd_render_queue_export_frame.png", final_rgb)
        overlay_frame = _save_rgba(out / "mmd_render_queue_overlay.png", overlay_rgba)
    else:
        export_delta = {"ok": False, "error": "missing_export_frame"}
        baseline_frame = ""
        export_frame = ""
        overlay_frame = ""

    final_thread_segments = list(getattr(final_thread, "_segments", []) or []) if "final_thread" in locals() else []
    final_thread_mmd_tracks = list(getattr(final_thread, "_mmd_tracks", []) or []) if "final_thread" in locals() else []
    checks = {
        "render_queue_job_queued": len(final_items) == 1,
        "render_queue_two_mmd_tracks": len(getattr(editor_with_mmd, "_mmd_tracks", []) or []) == 2,
        "baseline_export_ok": bool(baseline_result.get("ok")) and baseline.exists() and baseline.stat().st_size > 4096,
        "mmd_export_ok": bool(final_result.get("ok")) and final.exists() and final.stat().st_size > 4096,
        "thread_segments_match_trimmed_speed_range": final_thread_segments == expected_segments,
        "thread_receives_two_mmd_tracks": len(final_thread_mmd_tracks) == 2,
        "mmd_prerender_alpha_mov_created": bool(final_pre_rendered) and any(size > 4096 for size in final_pre_render_sizes),
        "preview_overlay_two_tracks_visible": len(render_item_track_ids) == 2,
        "preview_overlay_alpha_visible": bool(alpha.get("ok")),
        "export_composite_changes_mmd_region": bool(export_delta.get("ok")),
        "pre_render_progress_reaches_preface": any(value >= 30 for value in progress_values),
    }
    failures = [{"check": key, "message": "check failed"} for key, value in checks.items() if not value]
    payload = {
        "ok": not failures,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "kind": "mmd_render_queue_export_qa",
        "manifest": str(resolved_manifest),
        "entry_id": str(entry.get("id") or ""),
        "model_path": str(model_path),
        "motion_path": str(motion_path or ""),
        "width": width,
        "height": height,
        "duration_ms": duration_ms,
        "fps": fps,
        "segments": expected_segments,
        "sample_output_ms": sample_output_ms,
        "sample_project_ms": sample_project_ms,
        "summary": {
            "checks": len(checks),
            "passing": sum(1 for value in checks.values() if value),
            "failing": len(failures),
            "queued_jobs": len(final_items),
            "mmd_track_count": len(getattr(editor_with_mmd, "_mmd_tracks", []) or []),
            "render_item_track_ids": render_item_track_ids,
            "pre_render_count": len(final_pre_rendered),
            "pre_render_sizes": final_pre_render_sizes,
            "progress_values": list(progress_values),
            "alpha_coverage": alpha.get("alpha_coverage", 0.0),
            "export_inside_mean_abs_diff": export_delta.get("inside_mean_abs_diff", 0.0),
            "export_outside_mean_abs_diff": export_delta.get("outside_mean_abs_diff", 0.0),
        },
        "checks": checks,
        "alpha_metrics": alpha,
        "export_delta": export_delta,
        "baseline_export": baseline_result,
        "mmd_export": final_result,
        "baseline_probe": {key: value for key, value in baseline_probe.items() if key != "rgb"},
        "final_probe": {key: value for key, value in final_probe.items() if key != "rgb"},
        "outputs": {
            "out_dir": str(out),
            "source": str(source),
            "baseline_video": str(baseline),
            "export_video": str(final),
            "baseline_frame": baseline_frame,
            "export_frame": export_frame,
            "overlay_rgba": overlay_frame,
        },
        "failures": failures,
    }
    report.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    payload["report"] = str(report)
    return payload


def run_mmd_long_project_export_qa(
    *,
    manifest: str | Path = DEFAULT_MMD_QA_MANIFEST,
    entry_id: str = DEFAULT_MMD_RENDER_QUEUE_ENTRY_ID,
    out_dir: str | Path = DEFAULT_MMD_RENDER_QUEUE_QA_OUT_DIR,
    report_path: str | Path = DEFAULT_MMD_LONG_PROJECT_EXPORT_QA_REPORT,
    width: int = 480,
    height: int = 270,
    duration_ms: int = 10000,
    fps: int = 12,
) -> dict[str, Any]:
    """Run a longer render-queue export path with speed splits and two MMD actors."""
    import numpy as np

    from app.mmd.offscreen_export import MMDOffscreenGLRenderer
    from app.project_player import ProjectPlayer

    _ensure_qapplication()
    resolved_manifest = resolve_mmd_qa_path(manifest)
    out = Path(out_dir).expanduser().resolve()
    report = Path(report_path).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    width = max(320, int(width or 480))
    height = max(180, int(height or 270))
    duration_ms = max(8000, int(duration_ms or 10000))
    fps = max(6, min(30, int(fps or 12)))

    entry = select_mmd_editor_composite_entry(resolved_manifest, entry_id=entry_id)
    model_path, motion_path = _entry_paths(entry)
    source = out / "mmd_long_project_source.mp4"
    baseline = out / "mmd_long_project_baseline.mp4"
    final = out / "mmd_long_project_export.mp4"
    for path in (source, baseline, final):
        try:
            path.unlink()
        except OSError:
            pass
    _write_synthetic_video(source, width=width, height=height, fps=fps, duration_ms=duration_ms)

    active_start = 500
    active_end = duration_ms - 500
    timeline_markers = [
        {"ms": active_start, "label": "LongProject"},
        {"ms": active_end, "label": "End"},
    ]
    speed_segments = [
        (1800, 3000, 0.75),
        (5200, 6800, 1.75),
    ]
    long_tracks = _make_render_queue_mmd_tracks(
        model_path,
        motion_path,
        count=2,
        start_ms=active_start,
        end_ms=active_end,
        prefix="mmd_long_project",
    )
    if len(long_tracks) >= 2:
        long_tracks[1]["start_ms"] = 2500
        long_tracks[1]["end_ms"] = duration_ms - 1000
        long_tracks[1]["duration_ms"] = int(long_tracks[1]["end_ms"]) - int(long_tracks[1]["start_ms"])
        long_tracks[1]["playback"]["motion_start_ms"] = 700

    editor_with_mmd = _fake_editor(
        source_path=source,
        out_dir=out,
        model_path=model_path,
        motion_path=motion_path,
        with_mmd=True,
        source_duration_ms=duration_ms,
        timeline_markers=timeline_markers,
        speed_segments=speed_segments,
        mmd_tracks_override=long_tracks,
        export_resolution=(width, height),
        export_fps=fps,
    )
    editor_without_mmd = _fake_editor(
        source_path=source,
        out_dir=out,
        model_path=model_path,
        motion_path=motion_path,
        with_mmd=False,
        source_duration_ms=duration_ms,
        timeline_markers=timeline_markers,
        speed_segments=speed_segments,
        export_resolution=(width, height),
        export_fps=fps,
    )
    final_call = _capture_batch_export_call(editor_with_mmd, out)
    baseline_call = _capture_batch_export_call(editor_without_mmd, out)
    final_items = list(final_call.get("items") or [])
    baseline_items = list(baseline_call.get("items") or [])
    final_export_fn = final_call.get("export_fn")
    baseline_export_fn = baseline_call.get("export_fn")
    final_result: dict[str, Any] = {"ok": False, "error": "missing_export_fn"}
    baseline_result: dict[str, Any] = {"ok": False, "error": "missing_export_fn"}
    final_pre_rendered: list[Any] = []
    final_pre_render_sizes: list[int] = []
    progress_values: list[int] = []

    if callable(baseline_export_fn) and baseline_items:
        item = baseline_items[0]
        baseline_thread = baseline_export_fn(
            int(getattr(item, "in_ms", 0) or 0),
            int(getattr(item, "out_ms", 0) or 0),
            str(baseline),
            progress_cb=None,
        )
        baseline_result = _run_export(baseline_thread)
    if callable(final_export_fn) and final_items:
        item = final_items[0]
        final_thread = final_export_fn(
            int(getattr(item, "in_ms", 0) or 0),
            int(getattr(item, "out_ms", 0) or 0),
            str(final),
            progress_cb=lambda value: progress_values.append(int(value)),
        )
        final_pre_rendered = list(getattr(final_thread, "_mmd_pre_rendered", []) or [])
        final_pre_render_sizes = [
            int(Path(path).stat().st_size) if Path(path).exists() else 0
            for path, _start, _end in final_pre_rendered
        ]
        final_result = _run_export(final_thread)

    final_thread_segments = list(getattr(final_thread, "_segments", []) or []) if "final_thread" in locals() else []
    total_output_ms = int(sum((int(e) - int(s)) / max(float(sp), 0.001) for s, e, sp in final_thread_segments) + 0.5)
    sample_output_ms = sorted(
        {
            max(0, min(total_output_ms - 1, 600)),
            max(0, min(total_output_ms - 1, total_output_ms // 2)),
            max(0, min(total_output_ms - 1, total_output_ms - 600)),
        }
    )

    samples: list[dict[str, Any]] = []
    player = ProjectPlayer()
    renderer = MMDOffscreenGLRenderer()
    try:
        player.set_mmd_tracks(list(getattr(editor_with_mmd, "_mmd_tracks", []) or []))
        for output_ms in sample_output_ms:
            project_ms = _project_ms_for_output_ms(output_ms, final_thread_segments)
            items = player._mmd_overlay_items(project_ms, animate=True)
            render_item_track_ids = [str(item.get("track_id") or "") for item in list(items or [])]
            overlay_rgba = renderer.render_array(items, width, height) if items else None
            if overlay_rgba is None:
                overlay_rgba = np.zeros((height, width, 4), dtype=np.uint8)
            overlay_rgba = np.ascontiguousarray(overlay_rgba[:, :, :4], dtype=np.uint8)
            alpha = _alpha_metrics(overlay_rgba)
            frame_index = _sample_frame_index(output_ms, fps)
            baseline_probe = _read_video_frame(baseline, frame_index=frame_index) if baseline.exists() else {"ok": False, "error": "missing_baseline"}
            final_probe = _read_video_frame(final, frame_index=frame_index) if final.exists() else {"ok": False, "error": "missing_final"}
            if bool(baseline_probe.get("ok")) and bool(final_probe.get("ok")):
                baseline_rgb = _strip_rgb_from_probe(baseline_probe)
                final_rgb = _strip_rgb_from_probe(final_probe)
                export_delta = _composite_delta_metrics(baseline_rgb, final_rgb, overlay_rgba)
                sample_name = f"{output_ms:05d}ms"
                baseline_frame = _save_rgb(out / f"mmd_long_project_baseline_{sample_name}.png", baseline_rgb)
                export_frame = _save_rgb(out / f"mmd_long_project_export_{sample_name}.png", final_rgb)
                overlay_frame = _save_rgba(out / f"mmd_long_project_overlay_{sample_name}.png", overlay_rgba)
            else:
                export_delta = {"ok": False, "error": "missing_export_frame"}
                baseline_frame = ""
                export_frame = ""
                overlay_frame = ""
            active_ids = [
                str(track.get("id") or "")
                for track in list(getattr(editor_with_mmd, "_mmd_tracks", []) or [])
                if int(track.get("start_ms", 0) or 0) <= project_ms < int(track.get("end_ms", 0) or 0)
            ]
            samples.append(
                {
                    "ok": bool(active_ids) and bool(alpha.get("ok")) and bool(export_delta.get("ok")),
                    "output_ms": int(output_ms),
                    "project_ms": int(project_ms),
                    "expected_active_track_ids": active_ids,
                    "render_item_track_ids": render_item_track_ids,
                    "alpha_metrics": alpha,
                    "export_delta": export_delta,
                    "baseline_probe": {key: value for key, value in baseline_probe.items() if key != "rgb"},
                    "final_probe": {key: value for key, value in final_probe.items() if key != "rgb"},
                    "baseline_frame": baseline_frame,
                    "export_frame": export_frame,
                    "overlay_rgba": overlay_frame,
                }
            )
    finally:
        player.release()

    checks = {
        "render_queue_job_queued": len(final_items) == 1,
        "long_project_duration": duration_ms >= 8000 and total_output_ms >= 6500,
        "trimmed_speed_segments_preserved": len(final_thread_segments) >= 5,
        "two_mmd_tracks_present": len(getattr(editor_with_mmd, "_mmd_tracks", []) or []) == 2,
        "baseline_export_ok": bool(baseline_result.get("ok")) and baseline.exists() and baseline.stat().st_size > 4096,
        "mmd_export_ok": bool(final_result.get("ok")) and final.exists() and final.stat().st_size > 4096,
        "mmd_prerender_alpha_mov_created": bool(final_pre_rendered) and any(size > 4096 for size in final_pre_render_sizes),
        "all_long_samples_ok": bool(samples) and all(bool(row.get("ok")) for row in samples),
        "pre_render_progress_reaches_preface": any(value >= 30 for value in progress_values),
    }
    failures = [{"check": key, "message": "check failed"} for key, value in checks.items() if not value]
    payload = {
        "ok": not failures,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "kind": "mmd_long_project_export_qa",
        "manifest": str(resolved_manifest),
        "entry_id": str(entry.get("id") or ""),
        "model_path": str(model_path),
        "motion_path": str(motion_path or ""),
        "width": width,
        "height": height,
        "duration_ms": duration_ms,
        "fps": fps,
        "segments": final_thread_segments,
        "total_output_ms": total_output_ms,
        "summary": {
            "checks": len(checks),
            "passing": sum(1 for value in checks.values() if value),
            "failing": len(failures),
            "queued_jobs": len(final_items),
            "mmd_track_count": len(getattr(editor_with_mmd, "_mmd_tracks", []) or []),
            "pre_render_count": len(final_pre_rendered),
            "pre_render_sizes": final_pre_render_sizes,
            "progress_values": list(progress_values),
            "sample_output_ms": sample_output_ms,
            "sample_project_ms": [int(row.get("project_ms", 0) or 0) for row in samples],
            "max_export_inside_mean_abs_diff": max(
                [float(row.get("export_delta", {}).get("inside_mean_abs_diff", 0.0) or 0.0) for row in samples]
                or [0.0]
            ),
            "max_export_outside_mean_abs_diff": max(
                [float(row.get("export_delta", {}).get("outside_mean_abs_diff", 0.0) or 0.0) for row in samples]
                or [0.0]
            ),
        },
        "checks": checks,
        "baseline_export": baseline_result,
        "mmd_export": final_result,
        "samples": samples,
        "outputs": {
            "out_dir": str(out),
            "source": str(source),
            "baseline_video": str(baseline),
            "export_video": str(final),
        },
        "failures": failures,
    }
    report.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    payload["report"] = str(report)
    return payload
