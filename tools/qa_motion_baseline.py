"""Capture the pre-Motion-Designer project, playback, and OpenGL baseline.

The report is reproducible and does not modify a user project. It performs a
minimal .tgp save-load-save round trip, decodes frames from a durable QA video,
and records the current editor OpenGL source contract. The generated report is
disposable and belongs under debugCapture.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import statistics
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_MEDIA = ROOT / "qa_corpus" / "assets" / "qa_motion_720p.mp4"
DEFAULT_OUTPUT = ROOT / "debugCapture" / "motion_designer" / "baseline.json"


class _PlayerStub:
    REFERENCE_FPS = 30.0

    def __init__(self) -> None:
        self._position_ms = 0

    def position(self) -> int:
        return self._position_ms

    def set_position(self, value: int) -> None:
        self._position_ms = int(value)

    def pause(self) -> None:
        pass

    def set_spine_actor_tracks(self, _tracks) -> None:
        pass

    def set_live2d_actor_tracks(self, _tracks) -> None:
        pass

    def set_ar_pbr_tracks(self, _tracks) -> None:
        pass

    def set_mmd_tracks(self, _tracks) -> None:
        pass


class _LayoutStub:
    def removeWidget(self, _widget) -> None:
        pass


class _SubtitleLayerStub:
    on_change = None

    def items(self) -> list[Any]:
        return []


class _SubtitlePanelStub:
    def __init__(self) -> None:
        self.layer = _SubtitleLayerStub()


class _EditorStub:
    """Smallest editor surface accepted by current project_io."""

    def __init__(self) -> None:
        self._player = _PlayerStub()
        self._project_settings = {
            "name": "Motion Designer M0 Baseline",
            "canvas_width": 1920,
            "canvas_height": 1080,
            "fps": 30.0,
        }
        self._px_per_sec = 40.0
        self._global_in_ms = -1
        self._global_out_ms = -1
        self._tracks = []
        self._track_rows = {}
        self._audio_tracks = []
        self._audio_rows = {}
        self._tracks_layout = _LayoutStub()
        self._subtitle_panel = _SubtitlePanelStub()
        self._next_track_id = 1
        self._next_audio_track_id = 1
        self._next_audio_clip_id = 1
        self._audio_mixer_snapshots = []
        self._music_compositions = {}
        self._spine_actor_tracks = []
        self._live2d_actor_tracks = []
        self._ar_pbr_tracks = []
        self._mmd_tracks = []
        self._next_actor_id = 1
        self._next_live2d_id = 1
        self._next_ar_pbr_id = 1
        self._next_mmd_id = 1

    def _change_zoom(self, value: float) -> None:
        self._px_per_sec *= float(value)

    def _set_global_in(self, value: int) -> None:
        self._global_in_ms = int(value)

    def _set_global_out(self, value: int) -> None:
        self._global_out_ms = int(value)

    def _refresh_player_tracks(self) -> None:
        pass

    def _update_tracks_host_width(self) -> None:
        pass

    def _clear_global_markers(self) -> None:
        pass

    def setWindowTitle(self, _title: str) -> None:
        pass


def _canonical_project(doc: dict[str, Any]) -> dict[str, Any]:
    canonical = json.loads(json.dumps(doc))
    canonical.pop("saved_at", None)
    settings = canonical.get("project_settings") or {}
    export = canonical.get("export") or {}
    width = int(settings.get("canvas_width", 0) or 0)
    height = int(settings.get("canvas_height", 0) or 0)
    fps = float(settings.get("fps", 0.0) or 0.0)
    # project_io derives export defaults from project settings while loading.
    # Normalize that known legacy behavior without hiding any other drift.
    if export.get("resolution") is None and width > 0 and height > 0:
        export["resolution"] = [width, height]
    if float(export.get("fps", 0.0) or 0.0) <= 0.0 and fps > 0.0:
        export["fps"] = fps
    canonical["export"] = export
    return canonical


def _changed_top_level_keys(first: dict[str, Any], second: dict[str, Any]) -> list[str]:
    keys = set(first) | set(second)
    return sorted(key for key in keys if first.get(key) != second.get(key))


def probe_project_roundtrip() -> dict[str, Any]:
    from PySide6.QtCore import QCoreApplication

    from app.project_io import EXTENSION, FORMAT_VERSION, load_project, save_project

    app = QCoreApplication.instance() or QCoreApplication([])
    del app
    with tempfile.TemporaryDirectory(prefix="tiger_motion_m0_") as tmp:
        first = Path(tmp) / "first.tgp"
        second = Path(tmp) / "second.tgp"
        source_editor = _EditorStub()
        source_editor._player.set_position(1250)
        save_project(source_editor, first)
        loaded_editor = _EditorStub()
        load_project(loaded_editor, first)
        save_project(loaded_editor, second)
        first_doc = json.loads(first.read_text(encoding="utf-8"))
        second_doc = json.loads(second.read_text(encoding="utf-8"))

    raw_changed_keys = _changed_top_level_keys(first_doc, second_doc)
    first_canonical = _canonical_project(first_doc)
    second_canonical = _canonical_project(second_doc)
    changed_keys = _changed_top_level_keys(first_canonical, second_canonical)
    canonical_equal = not changed_keys
    return {
        "ok": canonical_equal,
        "format_version": FORMAT_VERSION,
        "extension": EXTENSION,
        "canonical_equal": canonical_equal,
        "changed_top_level_keys": changed_keys,
        "raw_changed_top_level_keys": raw_changed_keys,
        "normalization_rules": ["saved_at", "export defaults derived from project_settings"],
        "top_level_keys": sorted(first_doc),
        "motion_compositions_present": "motion_compositions" in first_doc,
        "playhead_ms": int(second_doc.get("playhead_ms", -1)),
        "canvas": [
            int((second_doc.get("project_settings") or {}).get("canvas_width", 0)),
            int((second_doc.get("project_settings") or {}).get("canvas_height", 0)),
        ],
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def probe_playback(media_path: Path, *, sample_count: int = 12) -> dict[str, Any]:
    from app.video_decoder import open_decoder

    media_path = media_path.resolve()
    if not media_path.is_file():
        return {"ok": False, "path": str(media_path), "error": "media_not_found"}

    started = time.perf_counter()
    decoder = open_decoder(media_path, preview_height=720)
    open_ms = (time.perf_counter() - started) * 1000.0
    if decoder is None:
        return {"ok": False, "path": str(media_path), "error": "decoder_open_failed"}

    timings: list[float] = []
    frames: list[tuple[int, int]] = []
    try:
        for _index in range(max(0, int(sample_count))):
            tick = time.perf_counter()
            frame = decoder.read_rgb()
            timings.append((time.perf_counter() - tick) * 1000.0)
            if frame is None:
                break
            height, width = frame.shape[:2]
            frames.append((int(width), int(height)))
    finally:
        decoder.release()

    decoded = len(frames)
    read_timings = timings[:decoded]
    return {
        "ok": decoded == max(0, int(sample_count)),
        "path": str(media_path),
        "path_relative": str(media_path.relative_to(ROOT)) if media_path.is_relative_to(ROOT) else "",
        "sha256": _sha256(media_path),
        "bytes": media_path.stat().st_size,
        "backend": type(decoder).__name__,
        "open_ms": round(open_ms, 3),
        "requested_frames": int(sample_count),
        "decoded_frames": decoded,
        "frame_size": list(frames[-1]) if frames else [0, 0],
        "mean_decode_ms": round(statistics.fmean(read_timings), 3) if read_timings else None,
        "p95_decode_ms": (
            round(sorted(read_timings)[max(0, math.ceil(len(read_timings) * 0.95) - 1)], 3)
            if read_timings
            else None
        ),
    }


def _class_methods(tree: ast.Module, name: str) -> set[str]:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            return {child.name for child in node.body if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))}
    return set()


def probe_opengl_contract() -> dict[str, Any]:
    preview_path = ROOT / "app" / "opengl_preview.py"
    workflow_path = ROOT / "app" / "video_editor_preview_frame_workflow.py"
    policy_path = ROOT / "app" / "qt_opengl_policy.py"
    parity_tool_path = ROOT / "tools" / "verify_export_parity.py"
    parity_spec_path = ROOT / "docs" / "SPEC_EXPORT_PARITY_AND_QA.md"
    preview_text = preview_path.read_text(encoding="utf-8")
    workflow_text = workflow_path.read_text(encoding="utf-8")
    policy_text = policy_path.read_text(encoding="utf-8")
    tree = ast.parse(preview_text)
    methods = _class_methods(tree, "OpenGLPreviewWidget")
    required_methods = {"initializeGL", "paintGL", "update_frame"}
    checks = {
        "qopenglwidget_surface": "class OpenGLPreviewWidget(QOpenGLWidget)" in preview_text,
        "required_methods": required_methods <= methods,
        "startup_prewarm": "def _prewarm_preview_gl_surface" in workflow_text,
        "shared_context_policy": "AA_ShareOpenGLContexts" in policy_text,
        "gpu_frame_bridge": "def _on_gpu_frame_ready" in workflow_text,
        "existing_export_parity_tool": parity_tool_path.is_file(),
        "export_parity_spec": parity_spec_path.is_file(),
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "preview_module": str(preview_path.relative_to(ROOT)),
        "workflow_module": str(workflow_path.relative_to(ROOT)),
        "policy_module": str(policy_path.relative_to(ROOT)),
        "existing_export_parity_tool": str(parity_tool_path.relative_to(ROOT)),
        "export_parity_spec": str(parity_spec_path.relative_to(ROOT)),
        "preview_methods": sorted(required_methods & methods),
        "runtime_context_probed": False,
        "runtime_context_note": "M0 records the existing source contract; pixel parity starts at M4.",
    }


def build_report(media_path: Path = DEFAULT_MEDIA, *, sample_count: int = 12) -> dict[str, Any]:
    project = probe_project_roundtrip()
    playback = probe_playback(Path(media_path), sample_count=sample_count)
    opengl = probe_opengl_contract()
    return {
        "schema": "tiger.motion_designer.baseline.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "milestone": "M0",
        "ok": bool(project.get("ok") and playback.get("ok") and opengl.get("ok")),
        "project_io": project,
        "playback": playback,
        "opengl_preview": opengl,
        "boundaries": {
            "durable_input_root": "qa_corpus/assets",
            "disposable_output_root": "debugCapture/motion_designer",
            "user_project_mutated": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--media", type=Path, default=DEFAULT_MEDIA)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--sample-count", type=int, default=12)
    args = parser.parse_args(argv)

    report = build_report(args.media, sample_count=max(0, int(args.sample_count)))
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
