from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication
import pytest

from app.actions.registry import ActionRegistry
from app.motion_designer.clip import MotionClip
from app.motion_designer.schema import MotionComposition, MotionLayer, SourceRef
from app.motion_designer.timeline_bridge import composition_time_ms, split_motion_clip
from app.project_player_motion_workflow import _apply_motion_clips
from app.video_exporter import VideoExportThread


def _motion_state():
    layer = MotionLayer(layer_type="shape", source=SourceRef(kind="shape", params={
        "width": 40, "height": 30, "fill": "#ff0000", "stroke_width": 0}), out_ms=1000)
    layer.transform.position.default = [50, 40]
    composition = MotionComposition(width=100, height=80, duration_ms=1000, layers=[layer])
    clip = MotionClip(composition_id=composition.id, start_ms=500, duration_ms=1000)
    return composition, clip


def _app():
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    return QApplication.instance() or QApplication([])


def test_motion_clip_split_and_time_mapping() -> None:
    composition, clip = _motion_state()
    left, right = split_motion_clip(clip, 900)
    assert left.end_ms == right.start_ms == 900
    assert right.source_in_ms == 400
    assert composition_time_ms(right, composition, 1000) == 500


def test_preview_and_export_motion_composite_match() -> None:
    app = _app()
    composition, clip = _motion_state()
    base = np.zeros((80, 100, 3), dtype=np.uint8)
    preview_owner = SimpleNamespace(_motion_clips=[clip], _motion_compositions={composition.id: composition},
                                    _motion_renderer=None)
    export_owner = SimpleNamespace(_motion_clips=[clip], _motion_compositions={composition.id: composition},
                                   _motion_renderer=None)
    preview = _apply_motion_clips(preview_owner, base, 600)
    exported = VideoExportThread._apply_motion_export_cpu(export_owner, base, 600)
    assert np.array_equal(preview, exported)
    assert preview[40, 50, 0] > 200
    app.processEvents()


def test_inactive_motion_clip_does_not_allocate_a_renderer() -> None:
    composition, clip = _motion_state()
    owner = SimpleNamespace(_motion_clips=[clip], _motion_compositions={composition.id: composition},
                            _motion_renderer=None)
    base = np.zeros((80, 100, 3), dtype=np.uint8)
    result = _apply_motion_clips(owner, base, 100)
    assert result is base
    assert owner._motion_renderer is None


class ActionOwner:
    def __init__(self) -> None:
        self._motion_compositions = {}
        self._motion_clips = []
        self._project_settings = {"canvas_width": 1280, "canvas_height": 720, "fps": 30}


def test_motion_clip_actions_create_place_and_split() -> None:
    owner = ActionOwner()
    registry = ActionRegistry(owner)
    created = registry.execute("motion.clip.create_from_timeline", {"name": "Lower Third", "start_ms": 1000,
                                                                     "duration_ms": 2000})
    clip_id = created.result["clip"]["id"]
    split = registry.execute("motion.clip.split", {"clip_id": clip_id, "timeline_ms": 2000})
    assert split.ok
    assert len(owner._motion_clips) == 2
    assert owner._motion_clips[0]["end_ms"] == owner._motion_clips[1]["start_ms"]


def test_project_io_preserves_motion_reference(tmp_path: Path) -> None:
    from tools.qa_motion_baseline import _EditorStub
    from app.project_io import load_project, save_project

    app = QCoreApplication.instance() or QCoreApplication([])
    composition, clip = _motion_state()
    source = _EditorStub()
    source._motion_compositions = {composition.id: composition}
    source._motion_clips = [clip.to_dict()]
    path = tmp_path / "motion.tgp"
    save_project(source, path)
    restored = _EditorStub()
    restored._motion_compositions = {}
    restored._motion_clips = []
    load_project(restored, path)
    assert list(restored._motion_compositions) == [composition.id]
    assert restored._motion_clips[0]["composition_id"] == composition.id
    assert restored._motion_clips[0]["start_ms"] == 500
    del app


def test_video_exporter_bakes_motion_clip_into_video(tmp_path: Path) -> None:
    import cv2

    app = _app()
    source = tmp_path / "source.mp4"
    writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*"mp4v"), 5.0, (100, 80))
    assert writer.isOpened()
    for _ in range(5):
        writer.write(np.zeros((80, 100, 3), dtype=np.uint8))
    writer.release()
    composition, clip = _motion_state()
    clip.start_ms = 0
    output = tmp_path / "baked.mp4"
    errors: list[str] = []
    exporter = VideoExportThread(source, output, [(0, 1000, 1.0)], target_width=100, target_height=80,
                                 target_fps=5, force_prerender_base=True,
                                 motion_compositions={composition.id: composition}, motion_clips=[clip.to_dict()])
    exporter.finished_error.connect(errors.append)
    exporter.run()
    assert not errors
    assert output.is_file() and output.stat().st_size > 0
    capture = cv2.VideoCapture(str(output))
    ok, bgr = capture.read()
    capture.release()
    assert ok and int(bgr[40, 50, 2]) > 120
    app.processEvents()
