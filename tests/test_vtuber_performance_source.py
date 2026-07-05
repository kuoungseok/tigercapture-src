from types import SimpleNamespace


def _clip(label, start, duration, *, kind="video", performance=False, path=None):
    return {
        "label": label,
        "kind": kind,
        "source_path": path or f"{label}.mp4",
        "timeline_in_ms": start,
        "duration_ms": duration,
        "performance_source": performance,
    }


def _track(label, clips, *, kind="video"):
    return {"label": label, "kind": kind, "clips": list(clips)}


def test_performance_source_ui_contract_names_main_ui_hooks():
    from app.vtuber.performance_source import (
        PERFORMANCE_SOURCE_MIME_TYPE,
        PERFORMANCE_SOURCE_TRACK_TYPE,
        performance_source_ui_contract,
    )

    contract = performance_source_ui_contract()

    assert contract["schema"] == "tigerstudio.vtuber.performance_source_ui.v1"
    assert contract["label"] == "Performance Source"
    assert contract["badge"] == "PERF"
    assert contract["media_pool"]["drag_mime_type"] == PERFORMANCE_SOURCE_MIME_TYPE
    assert contract["media_pool"]["program_output"] is False
    assert contract["timeline"]["track_type"] == PERFORMANCE_SOURCE_TRACK_TYPE
    assert contract["timeline"]["dedicated_track"] is True
    assert contract["timeline"]["program_output"] is False
    assert contract["studio"]["regions"] == ["program", "source_tracking", "avatar_mapping", "controls"]
    assert "vtuber.performance_source.add_clip" in contract["actions"]
    assert any("Program Output" in rule for rule in contract["rules"])


def test_program_background_prefers_capture_then_normal_media_and_skips_performance_source():
    from app.vtuber.performance_source import (
        PROGRAM_BACKGROUND_CAPTURE,
        choose_program_background_at,
    )

    tracks = [
        _track("Video", [_clip("background", 0, 30_000, path="game.mp4")]),
        _track("Performance Source", [_clip("trump", 0, 30_000, performance=True)], kind="vtuber_performance_source"),
        _track("Capture", [_clip("screen", 0, 30_000, kind="capture", path="capture://display")], kind="capture"),
    ]

    row = choose_program_background_at(tracks, 5_000)

    assert row["kind"] == PROGRAM_BACKGROUND_CAPTURE
    assert row["clip_label"] == "screen"
    assert row["skipped_performance_sources"][0]["clip_label"] == "trump"


def test_program_background_uses_green_chroma_when_only_performance_source_is_active():
    from app.vtuber.performance_source import (
        GREEN_CHROMA_RGBA,
        PROGRAM_BACKGROUND_CHROMA,
        choose_program_background_at,
    )

    tracks = [
        _track("Performance Source", [_clip("face_input", 0, 10_000, performance=True)], kind="vtuber_performance_source"),
    ]

    row = choose_program_background_at(tracks, 3_000)

    assert row["kind"] == PROGRAM_BACKGROUND_CHROMA
    assert row["color"] == list(GREEN_CHROMA_RGBA)
    assert row["skipped_performance_sources"][0]["clip_label"] == "face_input"


def test_active_performance_source_can_change_by_timeline_time():
    from app.vtuber.performance_source import active_performance_source_at

    tracks = [
        _track(
            "Performance Source",
            [
                _clip("webcam", 0, 10_000, performance=True),
                _clip("face_video", 10_000, 10_000, performance=True),
            ],
            kind="vtuber_performance_source",
        ),
    ]

    first = active_performance_source_at(tracks, 5_000)
    second = active_performance_source_at(tracks, 15_000)

    assert first["clip"]["label"] == "webcam"
    assert second["clip"]["label"] == "face_video"
    assert first["program_output"] is False
    assert second["program_output"] is False


def test_project_player_base_clip_selection_skips_performance_source_track(tmp_path):
    from app.project_player import ProjectPlayer

    background = tmp_path / "background.mp4"
    performance = tmp_path / "face.mp4"
    background.write_bytes(b"video")
    performance.write_bytes(b"perf")

    player = ProjectPlayer()
    bg_clip = SimpleNamespace(
        source_path=background,
        contains_timeline_ms=lambda ms: 0 <= ms < 10_000,
        is_nested_sequence=False,
    )
    perf_clip = SimpleNamespace(
        source_path=performance,
        performance_source=True,
        contains_timeline_ms=lambda ms: 0 <= ms < 10_000,
        is_nested_sequence=False,
    )
    bg_track = SimpleNamespace(id=1, source_path=None, clips=[bg_clip])
    perf_track = SimpleNamespace(id=2, source_path=None, clips=[perf_clip], track_type="vtuber_performance_source")
    player._tracks = [bg_track, perf_track]
    player._clips_view = {1: [bg_clip], 2: [perf_clip]}
    player._path_caps = {background: object(), performance: object()}

    track, clip = player._active_clip_at(1_000)

    assert track is bg_track
    assert clip is bg_clip


def test_video_clip_project_io_preserves_performance_source_flag(tmp_path):
    from app.project_io import _video_clip_from_dict, _video_clip_to_dict
    from app.timeline_model import VideoClip
    from app.vtuber.performance_source import is_performance_source_clip

    source = tmp_path / "face_input.mp4"
    source.write_bytes(b"video")
    clip = VideoClip(
        id=7,
        source_path=source,
        source_duration_ms=30_000,
        timeline_in_ms=2_000,
        source_in_ms=0,
        source_out_ms=30_000,
    )
    clip.performance_source = True
    clip.vtuber_performance_source = True
    clip.track_type = "vtuber_performance_source"
    clip.program_output = False

    row = _video_clip_to_dict(clip)
    restored = _video_clip_from_dict(row, None)

    assert row["performance_source"] is True
    assert row["program_output"] is False
    assert is_performance_source_clip(restored)
    assert getattr(restored, "program_output", True) is False
