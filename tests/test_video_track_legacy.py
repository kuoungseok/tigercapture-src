from __future__ import annotations

from pathlib import Path

from app.color_grading import ColorGrade
from app.i18n import tr
from app.timeline_model import ColorNode, NodeGraph, VideoClip
from app.video_track_legacy import VideoTrack, _ensure_video_clips


def _clip(clip_id: int, source_path: str | None) -> VideoClip:
    return VideoClip(
        id=clip_id,
        source_path=Path(source_path) if source_path is not None else None,
        source_duration_ms=1_000,
    )


def test_display_name_prefers_label_then_source_path_name():
    track = VideoTrack(id=1, source_path=Path("camera_a.mp4"))

    assert track.display_name == "camera_a.mp4"

    track.label = "Interview A"

    assert track.display_name == "Interview A"


def test_display_name_uses_clip_sources_when_track_has_no_source_path():
    track = VideoTrack(
        id=2,
        clips=[
            _clip(10, "angle_a.mov"),
            _clip(11, "angle_b.mov"),
        ],
    )

    assert track.display_name == "2 clips"


def test_display_name_empty_track_uses_translation_when_no_sources_exist():
    track = VideoTrack(
        id=3,
        clips=[
            _clip(20, None),
            _clip(21, None),
        ],
    )

    assert track.display_name == tr("veditor.track.empty")


def test_ensure_video_clips_marks_existing_clips_explicit_without_rebuild():
    kept_clip = _clip(30, "already_explicit.mp4")
    clips = [kept_clip]
    track = VideoTrack(
        id=4,
        source_path=Path("legacy_source.mp4"),
        duration_ms=5_000,
        clips=clips,
        clips_explicit=False,
    )

    _ensure_video_clips(track, force=False)

    assert track.clips_explicit is True
    assert track.clips is clips
    assert track.clips == [kept_clip]


def test_color_grade_property_delegates_to_node_graph_color_grade():
    initial = ColorGrade(brightness=5)
    graph = NodeGraph(color=ColorNode(grade=initial))
    track = VideoTrack(id=5, node_graph=graph)

    assert track.color_grade is initial

    replacement = ColorGrade(contrast=12)
    track.color_grade = replacement

    assert track.node_graph is graph
    assert graph.color.grade is replacement
    assert track.color_grade is replacement
