import json
from pathlib import Path

from app.live2d.actor_track import Live2DActorClip, Live2DActorTrack, Live2DKeyframe
from app.live2d_motion_storyboard import (
    apply_motion_storyboard_to_track,
    build_storyboard_ranges,
    list_live2d_motions,
)
from app.timeline_model import VideoClip


def _write_model(tmp_path: Path, motion_count: int = 4) -> Path:
    motions = []
    motion_dir = tmp_path / "motions"
    motion_dir.mkdir()
    for idx in range(motion_count):
        name = "idle.motion3.json" if idx == 0 else f"motion_{idx}.motion3.json"
        rel = f"motions/{name}"
        (tmp_path / rel).write_text("{}", encoding="utf-8")
        motions.append({"File": rel})
    model = {
        "Version": 3,
        "FileReferences": {
            "Moc": "model.moc3",
            "Textures": [],
            "Motions": {"Idle": motions[:1], "Tap": motions[1:]},
        },
    }
    path = tmp_path / "avatar.model3.json"
    path.write_text(json.dumps(model), encoding="utf-8")
    return path


def test_list_live2d_motions_reads_model3_motion3_entries(tmp_path: Path):
    model_path = _write_model(tmp_path, motion_count=3)

    motions = list_live2d_motions(model_path)

    assert len(motions) == 3
    assert motions[0].group == "Idle"
    assert "idle" in motions[0].label.lower()
    assert {m.group for m in motions} == {"Idle", "Tap"}


def test_storyboard_ranges_split_long_video_clip_to_cover_motions():
    ranges = build_storyboard_ranges(
        video_clips=[
            VideoClip(id=1, timeline_in_ms=0, source_duration_ms=9000),
        ],
        motion_count=4,
    )

    assert len(ranges) == 4
    assert ranges[0][0] == 0
    assert ranges[-1][1] == 9000
    assert all(end > start for start, end in ranges)


def test_apply_motion_storyboard_replaces_clip_with_cut_aligned_motion_clips(tmp_path: Path):
    model_path = _write_model(tmp_path, motion_count=4)
    source = Live2DActorClip(
        model_path=str(model_path),
        start_ms=0,
        duration_ms=9000,
        pos_x=0.55,
        scale=1.1,
    )
    source.kf_pos_x = [
        Live2DKeyframe(time_ms=0, value=0.50),
        Live2DKeyframe(time_ms=2500, value=0.60),
        Live2DKeyframe(time_ms=7000, value=0.45),
    ]
    source.mocap_parameter_keyframes = {
        "ParamAngleX": [
            {"time_ms": 500, "value": -10.0, "curve": "linear"},
            {"time_ms": 2500, "value": 12.0, "curve": "linear"},
            {"time_ms": 7200, "value": 4.0, "curve": "linear"},
        ]
    }
    track = Live2DActorTrack(id=2, clips=[source])
    video_clips = [
        VideoClip(id=10, timeline_in_ms=0, source_duration_ms=4000),
        VideoClip(id=11, timeline_in_ms=4000, source_duration_ms=5000),
    ]

    result = apply_motion_storyboard_to_track(track, source, video_clips=video_clips)

    assert result["ok"] is True
    assert result["created"] >= 4
    assert result["unique_motions_used"] == 4
    assert len(track.clips) == result["created"]
    assert track.clips[0].start_ms == 0
    assert track.clips[-1].end_ms == 9000
    assert all(c.motion_storyboard_payload["kind"] == "live2d_motion_storyboard" for c in track.clips)
    assert {c.motion_group for c in track.clips} == {"Idle", "Tap"}
    assert any(c.kf_pos_x for c in track.clips)
    assert any(c.mocap_parameter_keyframes.get("ParamAngleX") for c in track.clips)
    assert any(
        row["time_ms"] == 500
        for c in track.clips
        for row in c.mocap_parameter_keyframes.get("ParamAngleX", [])
    )
