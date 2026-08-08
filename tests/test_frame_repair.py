from pathlib import Path
from types import SimpleNamespace

import numpy as np


def _solid(value: int) -> np.ndarray:
    return np.full((4, 6, 3), int(value), dtype=np.uint8)


def test_hold_previous_repair_replaces_bad_frame() -> None:
    from app.frame_repair import apply_frame_repair_rgb, make_frame_repair_range
    from app.timeline_model import VideoClip

    clip = VideoClip(
        id=1,
        source_path=Path("source.mp4"),
        source_duration_ms=1000,
        frame_repairs=[
            make_frame_repair_range(
                source_start_ms=100,
                source_end_ms=200,
                method="hold_previous",
            )
        ],
    )
    frames = {
        0: _solid(12),
        1: _solid(200),
    }

    repaired, applied = apply_frame_repair_rgb(
        frames[1],
        clip=clip,
        source_ms=100,
        fps=10.0,
        frame_reader=lambda idx: frames.get(int(idx)),
    )

    assert applied is True
    assert int(repaired.mean()) == 12


def test_linear_repair_blends_surrounding_good_frames() -> None:
    from app.frame_repair import apply_frame_repair_rgb, make_frame_repair_range
    from app.timeline_model import VideoClip

    clip = VideoClip(
        id=1,
        source_path=Path("source.mp4"),
        source_duration_ms=1000,
        frame_repairs=[
            make_frame_repair_range(
                source_start_ms=100,
                source_end_ms=200,
                method="interpolate",
                algorithm="linear",
            )
        ],
    )
    frames = {
        0: _solid(10),
        1: _solid(250),
        2: _solid(110),
    }

    repaired, applied = apply_frame_repair_rgb(
        frames[1],
        clip=clip,
        source_ms=100,
        fps=10.0,
        frame_reader=lambda idx: frames.get(int(idx)),
    )

    assert applied is True
    assert int(repaired.mean()) == 60


def test_project_io_roundtrips_frame_repairs() -> None:
    from app.frame_repair import make_frame_repair_range
    from app.project_io import _video_clip_from_dict, _video_clip_to_dict
    from app.timeline_model import VideoClip

    clip = VideoClip(
        id=7,
        source_path=Path("source.mp4"),
        source_duration_ms=1000,
        frame_repairs=[
            make_frame_repair_range(
                source_start_ms=100,
                source_end_ms=200,
                method="interpolate",
                algorithm="linear",
                label="bad flash",
            )
        ],
    )

    restored = _video_clip_from_dict(_video_clip_to_dict(clip), None)

    assert restored.frame_repairs[0]["source_start_ms"] == 100
    assert restored.frame_repairs[0]["source_end_ms"] == 200
    assert restored.frame_repairs[0]["method"] == "interpolate"
    assert restored.frame_repairs[0]["algorithm"] == "linear"
    assert restored.frame_repairs[0]["label"] == "bad flash"


def test_action_registry_exposes_frame_repair_actions() -> None:
    from app.actions.registry import ActionRegistry

    actions = {row["id"] for row in ActionRegistry().list_actions()}

    assert "clip.frame_repair.list" in actions
    assert "clip.frame_repair.add" in actions
    assert "clip.frame_repair.remove" in actions


def test_frame_repair_actions_add_list_and_remove_ranges() -> None:
    from app.actions.registry import ActionRegistry
    from app.timeline_model import VideoClip, VideoTrack

    clip = VideoClip(
        id=10,
        source_path=Path("source.mp4"),
        source_duration_ms=1000,
        source_in_ms=0,
        source_out_ms=1000,
    )
    track = VideoTrack(id=1, clips=[clip])
    changes: list[str] = []
    refreshes: list[str] = []
    player_refreshes: list[str] = []
    owner = SimpleNamespace(
        _tracks=[track],
        _register_change=lambda label: changes.append(str(label)),
        _refresh_player_tracks=lambda: refreshes.append("tracks"),
        _update_tracks_host_width=lambda: None,
        _player=SimpleNamespace(refresh_current_frame=lambda: player_refreshes.append("frame")),
    )
    registry = ActionRegistry(owner)

    added = registry.execute(
        "clip.frame_repair.add",
        {
            "track_id": 1,
            "clip_id": 10,
            "source_start_ms": 100,
            "source_end_ms": 200,
            "method": "interpolate",
            "algorithm": "linear",
        },
    )
    repair_after_add = list(clip.frame_repairs)
    listed = registry.execute("clip.frame_repair.list", {"track_id": 1, "clip_id": 10})
    removed = registry.execute(
        "clip.frame_repair.remove",
        {
            "track_id": 1,
            "clip_id": 10,
            "repair_id": added.result["repair_id"],
        },
    )

    assert added.ok is True
    assert added.changed is True
    assert repair_after_add[0]["source_start_ms"] == 100
    assert repair_after_add[0]["source_end_ms"] == 200
    assert listed.result["repair_count"] == 1
    assert removed.ok is True
    assert removed.result["removed_count"] == 1
    assert clip.frame_repairs == []
    assert changes == ["Action add frame repair", "Action remove frame repair"]
    assert refreshes == ["tracks", "tracks"]
    assert player_refreshes == ["frame", "frame"]


def test_timeline_clip_shows_frame_fix_status_badge() -> None:
    from app.timeline_track_row import TrackRow

    clip = SimpleNamespace(
        timeline_in_ms=1000,
        timeline_out_ms=3000,
        video_filters=None,
        chroma_key=None,
        bg_removal=None,
        transition_out_type="",
        color_grade=None,
        node_graph=None,
        screenstudio_polish={},
        frame_repairs=[{"id": "repair_1", "source_start_ms": 100, "source_end_ms": 134}],
        is_nested_sequence=False,
        compound_group_id=None,
    )
    row = SimpleNamespace(
        track=SimpleNamespace(typography_actors=[], zoom_actors=[]),
        _effect_param_active=TrackRow._effect_param_active,
        _ranges_overlap=TrackRow._ranges_overlap,
    )

    labels = [badge[0] for badge in TrackRow._clip_status_badges(row, clip)]
    entries = TrackRow._clip_effect_strip_entries(row, clip)

    assert labels == ["Fix"]
    assert TrackRow._clip_status_badge_action("Fix") == "inspect"
    assert entries[0][0] == "FIX"
    assert entries[0][1] == "Frame Fix"


def test_split_clips_partitions_frame_repair_ranges() -> None:
    from app.frame_repair import make_frame_repair_range
    from app.timeline_model import VideoClip, split_clips_at_project_ms

    clip = VideoClip(
        id=1,
        source_path=Path("source.mp4"),
        source_duration_ms=10_000,
        source_in_ms=0,
        source_out_ms=10_000,
        frame_repairs=[
            make_frame_repair_range(
                source_start_ms=3000,
                source_end_ms=7000,
            )
        ],
    )

    left, right = split_clips_at_project_ms([clip], 5000)

    assert left.frame_repairs[0]["source_start_ms"] == 3000
    assert left.frame_repairs[0]["source_end_ms"] == 5000
    assert right.frame_repairs[0]["source_start_ms"] == 5000
    assert right.frame_repairs[0]["source_end_ms"] == 7000


def test_video_track_split_at_partitions_frame_repair_ranges_in_place() -> None:
    from app.frame_repair import make_frame_repair_range
    from app.timeline_model import VideoClip, VideoTrack

    clip = VideoClip(
        id=1,
        source_path=Path("source.mp4"),
        source_duration_ms=10_000,
        source_in_ms=0,
        source_out_ms=10_000,
        frame_repairs=[
            make_frame_repair_range(
                source_start_ms=3000,
                source_end_ms=7000,
            )
        ],
    )
    track = VideoTrack(id=1, clips=[clip])

    left, right = track.split_at(5000)

    assert left is clip
    assert left.frame_repairs[0]["source_start_ms"] == 3000
    assert left.frame_repairs[0]["source_end_ms"] == 5000
    assert right.frame_repairs[0]["source_start_ms"] == 5000
    assert right.frame_repairs[0]["source_end_ms"] == 7000


def test_cut_clip_window_partitions_frame_repair_ranges() -> None:
    from app.frame_repair import make_frame_repair_range
    from app.timeline_model import VideoClip
    from app.video_editor_nested_sequence import cut_clip_window

    clip = VideoClip(
        id=1,
        source_path=Path("source.mp4"),
        source_duration_ms=10_000,
        source_in_ms=0,
        source_out_ms=10_000,
        frame_repairs=[
            make_frame_repair_range(
                source_start_ms=3000,
                source_end_ms=7000,
            )
        ],
    )

    left, right = cut_clip_window([clip], 4000, 6000, track_offset_ms=0)

    assert left.frame_repairs[0]["source_start_ms"] == 3000
    assert left.frame_repairs[0]["source_end_ms"] == 4000
    assert right.frame_repairs[0]["source_start_ms"] == 6000
    assert right.frame_repairs[0]["source_end_ms"] == 7000
