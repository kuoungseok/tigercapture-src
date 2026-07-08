from __future__ import annotations

from app.ai_action_command import build_ai_action_command_plan


def _snapshot(tmp_path):
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"fake")
    return {
        "current_position_ms": 2000,
        "media_pool": [{"path": str(media), "kind": "video", "name": "clip.mp4", "duration_ms": 5000}],
        "video_tracks": [
            {
                "id": 1,
                "clips": [
                    {
                        "id": 10,
                        "timeline_in_ms": 0,
                        "timeline_out_ms": 5000,
                        "duration_ms": 5000,
                    }
                ],
            }
        ],
        "audio_tracks": [],
        "selected_clips": [{"track_kind": "video", "track_id": 1, "clip_id": 10}],
    }


def _audio_snapshot(tmp_path):
    snapshot = _snapshot(tmp_path)
    audio = tmp_path / "voice.wav"
    audio.write_bytes(b"fake")
    snapshot["media_pool"].append(
        {"path": str(audio), "kind": "audio", "name": "voice.wav", "duration_ms": 5000}
    )
    snapshot["audio_tracks"] = [
        {
            "id": 2,
            "clips": [
                {
                    "id": 20,
                    "offset_ms": 0,
                    "end_ms": 5000,
                    "duration_ms": 5000,
                }
            ],
        }
    ]
    snapshot["selected_clips"] = [{"track_kind": "audio", "track_id": 2, "clip_id": 20}]
    return snapshot


def test_ai_action_command_routes_media_pool_video_to_timeline(tmp_path):
    plan = build_ai_action_command_plan("미디어 풀의 동영상을 타임라인에 배치해줘", _snapshot(tmp_path))

    assert plan is not None
    assert plan.steps[0]["action"] == "media.import_to_timeline"
    assert plan.steps[0]["params"]["kind"] == "video"
    assert plan.steps[0]["params"]["track_id"] == 1


def test_ai_action_command_routes_split_marker_and_speed(tmp_path):
    snapshot = _snapshot(tmp_path)

    split = build_ai_action_command_plan("여기서 잘라줘", snapshot)
    marker = build_ai_action_command_plan("마커 추가", snapshot)
    speed = build_ai_action_command_plan("선택한 클립 2배속으로", snapshot)

    assert split is not None
    assert split.steps[0]["action"] == "timeline.split"
    assert split.steps[0]["params"] == {"track_id": 1, "at_ms": 2000}
    assert marker is not None
    assert marker.steps[0]["action"] == "timeline.marker.add"
    assert marker.steps[0]["params"]["ms"] == 2000
    assert speed is not None
    assert speed.steps[0]["action"] == "clip.set_speed"
    assert speed.steps[0]["params"]["speed"] == 2.0


def test_ai_action_command_routes_clip_text_and_color(tmp_path):
    snapshot = _snapshot(tmp_path)

    title = build_ai_action_command_plan('"오프닝" 타이틀 넣어줘', snapshot)
    grade = build_ai_action_command_plan("선택 클립을 밝게 색보정해줘", snapshot)

    assert title is not None
    assert title.steps[0]["action"] == "text.add"
    assert title.steps[0]["params"]["text"] == "오프닝"
    assert grade is not None
    assert grade.steps[0]["action"] == "clip.set_color_grade"
    assert grade.steps[0]["params"]["grade"]["brightness"] > 0


def test_ai_action_command_routes_nle_polish_edit_actions(tmp_path):
    snapshot = _snapshot(tmp_path)
    snapshot["video_tracks"][0]["clips"].append(
        {
            "id": 11,
            "timeline_in_ms": 5000,
            "timeline_out_ms": 8000,
            "duration_ms": 3000,
        }
    )

    slip = build_ai_action_command_plan("선택 클립 슬립 500ms", snapshot)
    slide = build_ai_action_command_plan("선택 클립을 슬라이드 편집 200ms", snapshot)
    roll = build_ai_action_command_plan("선택 클립 경계를 롤 편집 300ms", snapshot)

    assert slip is not None
    assert slip.steps[0]["action"] == "clip.slip"
    assert slip.steps[0]["params"]["delta_ms"] == 500
    assert slide is not None
    assert slide.steps[0]["action"] == "clip.slide"
    assert slide.steps[0]["params"]["delta_ms"] == 200
    assert roll is not None
    assert roll.steps[0]["action"] == "clip.roll"
    assert roll.steps[0]["params"]["left_clip_id"] == 10
    assert roll.steps[0]["params"]["right_clip_id"] == 11


def test_ai_action_command_routes_linked_audio_edit_actions(tmp_path):
    snapshot = _snapshot(tmp_path)

    link = build_ai_action_command_plan("선택 클립 오디오 링크", snapshot)
    unlink = build_ai_action_command_plan("선택 클립 오디오 링크 해제", snapshot)
    sync = build_ai_action_command_plan("선택 클립 싱크 오프셋 200ms", snapshot)
    jcut = build_ai_action_command_plan("선택 클립 J컷 500ms", snapshot)
    lcut = build_ai_action_command_plan("선택 클립 L컷 700ms", snapshot)

    assert link is not None
    assert link.steps[0]["action"] == "clip.link_audio"
    assert link.steps[0]["params"]["nearest"] is True
    assert unlink is not None
    assert unlink.steps[0]["action"] == "clip.unlink_audio"
    assert sync is not None
    assert sync.steps[0]["action"] == "clip.set_sync_offset"
    assert sync.steps[0]["params"]["sync_offset_ms"] == 200
    assert jcut is not None
    assert jcut.steps[0]["action"] == "clip.j_cut"
    assert jcut.steps[0]["params"]["extend_ms"] == 500
    assert lcut is not None
    assert lcut.steps[0]["action"] == "clip.l_cut"
    assert lcut.steps[0]["params"]["extend_ms"] == 700


def test_ai_action_command_routes_sound_editor_actions(tmp_path):
    snapshot = _audio_snapshot(tmp_path)

    cleanup = build_ai_action_command_plan("clean up the voice audio", snapshot)
    ai = build_ai_action_command_plan("apply ACE-Step AI master to audio", snapshot)
    loudness = build_ai_action_command_plan("audio loudness report", snapshot)
    stems = build_ai_action_command_plan("separate vocal stems", snapshot)
    louder = build_ai_action_command_plan("make audio louder by 3db", snapshot)
    korean_cleanup = build_ai_action_command_plan(
        "\uc0ac\uc6b4\ub4dc \ubaa9\uc18c\ub9ac \uc815\ub9ac\ud574\uc918",
        snapshot,
    )

    assert cleanup is not None
    assert cleanup.steps[0]["action"] == "audio.sound_editor.apply_effects"
    assert cleanup.steps[0]["params"]["track_id"] == 2
    assert cleanup.steps[0]["params"]["clip_id"] == 20
    assert cleanup.steps[0]["params"]["effects"]["dialogue_cleanup"]["enabled"] is True
    assert ai is not None
    assert ai.steps[0]["action"] == "audio.sound_editor.apply_ai_preset"
    assert ai.steps[0]["params"]["preset"] == "ACE-Step"
    assert loudness is not None
    assert loudness.steps[0]["action"] == "audio.loudness_report"
    assert stems is not None
    assert stems.steps[0]["action"] == "audio.separate_stems"
    assert louder is not None
    assert louder.steps[0]["action"] == "audio.sound_editor.apply_effects"
    assert louder.steps[0]["params"]["basic"]["gain_db"] == 3.0
    assert korean_cleanup is not None
    assert korean_cleanup.steps[0]["action"] == "audio.sound_editor.apply_effects"


def test_ai_action_command_routes_music_generation_to_music_lab(tmp_path):
    snapshot = _snapshot(tmp_path)

    korean = build_ai_action_command_plan(
        "\ud14c\ud06c\ub370\ubaa8\uc6a9 30\ucd08 \ubc30\uacbd\uc74c\uc545 \ub9cc\ub4e4\uc5b4\uc918",
        snapshot,
    )
    english = build_ai_action_command_plan("make a 12s lofi bgm at the playhead", snapshot)

    assert korean is not None
    assert korean.steps[0]["action"] == "music.compose_to_timeline"
    assert korean.steps[0]["params"]["duration_ms"] == 30000
    assert korean.steps[0]["params"]["genre"] == "electronic"
    assert korean.steps[0]["params"]["at_ms"] == 0
    assert korean.steps[0]["params"]["auto_balance"] is True
    assert english is not None
    assert english.steps[0]["action"] == "music.compose_to_timeline"
    assert english.steps[0]["params"]["duration_ms"] == 12000
    assert english.steps[0]["params"]["genre"] == "lofi"
    assert english.steps[0]["params"]["at_ms"] == 2000
    assert english.steps[0]["params"]["update_existing"] is True


def test_ai_action_command_routes_music_lab_edit_commands(tmp_path):
    snapshot = _snapshot(tmp_path)
    snapshot["music_compositions"] = [
        {
            "id": "music_demo",
            "prompt": "tech demo BGM",
            "genre": "electronic",
            "mood": "confident",
            "duration_ms": 30000,
        }
    ]
    snapshot["audio_tracks"] = [
        {"id": 11, "music_composition_id": "music_demo", "music_role": "drums", "clips": []},
        {"id": 12, "music_composition_id": "music_demo", "music_role": "bass", "clips": []},
        {"id": 13, "music_composition_id": "music_demo", "music_role": "chords", "clips": []},
    ]
    snapshot["music_lab_selection"] = {
        "composition_id": "music_demo",
        "role": "bass",
        "section_name": "build",
        "section_duration_ms": 8000,
        "note_count": 12,
    }

    stronger = build_ai_action_command_plan("make the main music section stronger", snapshot)
    selected_stronger = build_ai_action_command_plan("make the selected music section stronger", snapshot)
    remove_drums = build_ai_action_command_plan("remove drums from the music", snapshot)
    mute_selected = build_ai_action_command_plan("mute selected music track", snapshot)
    pad_only = build_ai_action_command_plan("pad only for the music", snapshot)
    midi = build_ai_action_command_plan("export midi", snapshot)

    assert stronger is not None
    assert [step["action"] for step in stronger.steps] == [
        "music.regenerate_section",
        "music.render_to_timeline",
        "music.mixer.auto_balance",
    ]
    assert stronger.steps[0]["params"]["composition_id"] == "music_demo"
    assert stronger.steps[0]["params"]["section_name"] == "main"
    assert stronger.steps[0]["params"]["intensity"] == 0.95
    assert stronger.steps[1]["params"]["update_existing"] is True
    assert selected_stronger is not None
    assert selected_stronger.steps[0]["action"] == "music.regenerate_section"
    assert selected_stronger.steps[0]["params"]["section_name"] == "build"
    assert remove_drums is not None
    assert remove_drums.steps[0]["action"] == "audio.track.mute"
    assert remove_drums.steps[0]["params"] == {"track_id": 11, "muted": True}
    assert mute_selected is not None
    assert mute_selected.steps[0]["action"] == "audio.track.mute"
    assert mute_selected.steps[0]["params"] == {"track_id": 12, "muted": True}
    assert pad_only is not None
    assert [step["params"]["muted"] for step in pad_only.steps] == [True, True, False]
    assert midi is not None
    assert midi.steps[0]["action"] == "music.export_midi"
    assert midi.steps[0]["params"]["composition_id"] == "music_demo"


def test_ai_action_command_routes_selection_group_move_actions(tmp_path):
    snapshot = _snapshot(tmp_path)

    move = build_ai_action_command_plan("move selected clips 250ms", snapshot)
    nudge = build_ai_action_command_plan("nudge selection -100ms", snapshot)
    frame_nudge = build_ai_action_command_plan("nudge selection 3 frames", snapshot)
    timeline_nudge = build_ai_action_command_plan("timeline nudge 80ms", snapshot)

    assert move is not None
    assert move.steps[0]["action"] == "selection.move"
    assert move.steps[0]["params"]["delta_ms"] == 250
    assert move.steps[0]["params"]["strict_links"] is True
    assert nudge is not None
    assert nudge.steps[0]["action"] == "selection.nudge"
    assert nudge.steps[0]["params"]["delta_ms"] == -100
    assert frame_nudge is not None
    assert frame_nudge.steps[0]["action"] == "selection.nudge_frames"
    assert frame_nudge.steps[0]["params"]["frames"] == 3
    assert timeline_nudge is not None
    assert timeline_nudge.steps[0]["action"] == "timeline.nudge"
    assert timeline_nudge.steps[0]["params"]["delta_ms"] == 80


def test_ai_action_command_routes_selection_range_action(tmp_path):
    snapshot = _snapshot(tmp_path)

    replace = build_ai_action_command_plan("select range 1s to 3s", snapshot)
    add = build_ai_action_command_plan("add select range 500ms 2500ms", snapshot)
    target_track = build_ai_action_command_plan("target video track 1 only", snapshot)
    clear_targets = build_ai_action_command_plan("clear track targets", snapshot)
    lift_range = build_ai_action_command_plan("lift range", snapshot)
    extract_range = build_ai_action_command_plan("extract range", snapshot)

    assert replace is not None
    assert replace.steps[0]["action"] == "selection.select_range"
    assert replace.steps[0]["params"]["start_ms"] == 1000
    assert replace.steps[0]["params"]["end_ms"] == 3000
    assert replace.steps[0]["params"]["mode"] == "replace"
    assert add is not None
    assert add.steps[0]["action"] == "selection.select_range"
    assert add.steps[0]["params"]["start_ms"] == 500
    assert add.steps[0]["params"]["end_ms"] == 2500
    assert add.steps[0]["params"]["mode"] == "add"
    assert target_track is not None
    assert target_track.steps[0]["action"] == "timeline.track_target.set"
    assert target_track.steps[0]["params"] == {
        "kind": "video",
        "track_id": 1,
        "enabled": True,
        "exclusive": True,
    }
    assert clear_targets is not None
    assert clear_targets.steps[0]["action"] == "timeline.track_target.clear"
    assert clear_targets.steps[0]["params"]["kind"] == "all"
    assert lift_range is not None
    assert lift_range.steps[0]["action"] == "timeline.lift"
    assert extract_range is not None
    assert extract_range.steps[0]["action"] == "timeline.extract"


def test_ai_action_command_routes_selection_focus_actions(tmp_path):
    snapshot = _snapshot(tmp_path)

    all_clips = build_ai_action_command_plan("select all clips", snapshot)
    first_clip = build_ai_action_command_plan("select first clip", snapshot)
    track = build_ai_action_command_plan("select video track", snapshot)

    assert all_clips is not None
    assert all_clips.steps[0]["action"] == "timeline.select_all"
    assert all_clips.steps[0]["params"]["kind"] == "all"
    assert first_clip is not None
    assert first_clip.steps[0]["action"] == "clip.select"
    assert first_clip.steps[0]["params"]["track_id"] == 1
    assert first_clip.steps[0]["params"]["clip_id"] == 10
    assert track is not None
    assert track.steps[0]["action"] == "track.select"
    assert track.steps[0]["params"]["kind"] == "video"
    assert track.steps[0]["params"]["track_id"] == 1


def test_ai_action_command_routes_edit_point_jump_action(tmp_path):
    snapshot = _snapshot(tmp_path)

    next_jump = build_ai_action_command_plan("next edit", snapshot)
    previous_jump = build_ai_action_command_plan("previous cut", snapshot)

    assert next_jump is not None
    assert next_jump.steps[0]["action"] == "timeline.jump_edit_point"
    assert next_jump.steps[0]["params"]["direction"] == "next"
    assert next_jump.steps[0]["params"]["track_kind"] == "video"
    assert previous_jump is not None
    assert previous_jump.steps[0]["action"] == "timeline.jump_edit_point"
    assert previous_jump.steps[0]["params"]["direction"] == "previous"


def test_ai_action_command_routes_timeline_range_and_clip_audition(tmp_path):
    snapshot = _snapshot(tmp_path)

    mark_in = build_ai_action_command_plan("mark in", snapshot)
    mark_out = build_ai_action_command_plan("mark out", snapshot)
    clear = build_ai_action_command_plan("clear in out", snapshot)
    mark_selection = build_ai_action_command_plan("set in/out from selection", snapshot)
    jump_out = build_ai_action_command_plan("jump to out", snapshot)
    play_clip = build_ai_action_command_plan("play selected clip", snapshot)

    assert mark_in is not None
    assert mark_in.steps[0]["action"] == "timeline.set_in"
    assert mark_in.steps[0]["params"]["ms"] == 2000
    assert mark_out is not None
    assert mark_out.steps[0]["action"] == "timeline.set_out"
    assert mark_out.steps[0]["params"]["ms"] == 2000
    assert clear is not None
    assert clear.steps[0]["action"] == "timeline.clear_in_out"
    assert mark_selection is not None
    assert mark_selection.steps[0]["action"] == "timeline.set_in_out_from_selection"
    assert jump_out is not None
    assert jump_out.steps[0]["action"] == "timeline.jump_in_out"
    assert jump_out.steps[0]["params"]["edge"] == "out"
    assert play_clip is not None
    assert play_clip.steps[0]["action"] == "timeline.play_clip_range"
    assert play_clip.steps[0]["params"]["restore_playhead"] is True


def test_ai_action_command_routes_transport_actions(tmp_path):
    snapshot = _snapshot(tmp_path)

    context = build_ai_action_command_plan("show edit status", snapshot)
    nle_readiness = build_ai_action_command_plan("show professional NLE readiness", snapshot)
    source_state = build_ai_action_command_plan("show source monitor status", snapshot)
    record_state = build_ai_action_command_plan("show record monitor status", snapshot)
    load_source = build_ai_action_command_plan("load source monitor", snapshot)
    play = build_ai_action_command_plan("play", snapshot)
    pause = build_ai_action_command_plan("pause playback", snapshot)
    stop = build_ai_action_command_plan("stop playback", snapshot)
    next_frame = build_ai_action_command_plan("next frame", snapshot)
    previous_frame = build_ai_action_command_plan("previous frame", snapshot)
    shuttle = build_ai_action_command_plan("shuttle 2x", snapshot)
    fit = build_ai_action_command_plan("fit timeline", snapshot)
    undo = build_ai_action_command_plan("undo", snapshot)
    redo = build_ai_action_command_plan("redo", snapshot)

    assert context is not None
    assert context.steps[0]["action"] == "timeline.nle_status"
    assert nle_readiness is not None
    assert nle_readiness.steps[0]["action"] == "timeline.professional_nle_readiness"
    assert source_state is not None
    assert source_state.steps[0]["action"] == "source_monitor.state"
    assert record_state is not None
    assert record_state.steps[0]["action"] == "record_monitor.state"
    assert load_source is not None
    assert load_source.steps[0]["action"] == "source_monitor.load_media"
    assert load_source.steps[0]["params"]["kind"] == "video"
    assert play is not None
    assert play.steps[0]["action"] == "timeline.play"
    assert pause is not None
    assert pause.steps[0]["action"] == "timeline.pause"
    assert stop is not None
    assert stop.steps[0]["action"] == "timeline.stop"
    assert next_frame is not None
    assert next_frame.steps[0]["action"] == "timeline.step_frames"
    assert next_frame.steps[0]["params"]["frames"] == 1
    assert previous_frame is not None
    assert previous_frame.steps[0]["action"] == "timeline.step_frames"
    assert previous_frame.steps[0]["params"]["frames"] == -1
    assert shuttle is not None
    assert shuttle.steps[0]["action"] == "timeline.set_shuttle_rate"
    assert shuttle.steps[0]["params"]["rate"] == 2.0
    assert fit is not None
    assert fit.steps[0]["action"] == "timeline.fit"
    assert undo is not None
    assert undo.steps[0]["action"] == "history.undo"
    assert redo is not None
    assert redo.steps[0]["action"] == "history.redo"


def test_ai_action_command_routes_transition_and_creative_readiness(tmp_path):
    snapshot = _snapshot(tmp_path)

    readiness = build_ai_action_command_plan("show creative layer readiness", snapshot)
    apply_transition = build_ai_action_command_plan("add dip white transition", snapshot)
    clear_transition = build_ai_action_command_plan("clear transition", snapshot)

    assert readiness is not None
    assert readiness.steps[0]["action"] == "creative_layer.readiness"
    assert apply_transition is not None
    assert apply_transition.steps[0]["action"] == "transition.apply"
    assert apply_transition.steps[0]["params"]["track_id"] == 1
    assert apply_transition.steps[0]["params"]["clip_id"] == 10
    assert apply_transition.steps[0]["params"]["preset_id"] == "transition-dip-white"
    assert clear_transition is not None
    assert clear_transition.steps[0]["action"] == "transition.clear"
    assert clear_transition.steps[0]["params"]["clip_id"] == 10


def test_ai_action_command_routes_clip_clipboard_actions(tmp_path):
    snapshot = _snapshot(tmp_path)

    copy = build_ai_action_command_plan("copy selected clips", snapshot)
    cut = build_ai_action_command_plan("cut selected clips", snapshot)
    paste = build_ai_action_command_plan("paste clips", snapshot)
    insert = build_ai_action_command_plan("insert paste", snapshot)
    overwrite = build_ai_action_command_plan("overwrite paste", snapshot)
    three_insert = build_ai_action_command_plan("three point insert", snapshot)
    three_overwrite = build_ai_action_command_plan("three point overwrite", snapshot)

    assert copy is not None
    assert copy.steps[0]["action"] == "clip.copy"
    assert copy.steps[0]["params"]["use_selection"] is True
    assert cut is not None
    assert cut.steps[0]["action"] == "clip.cut_to_clipboard"
    assert cut.steps[0]["params"]["use_selection"] is True
    assert paste is not None
    assert paste.steps[0]["action"] == "clip.paste"
    assert insert is not None
    assert insert.steps[0]["action"] == "timeline.insert_clipboard"
    assert overwrite is not None
    assert overwrite.steps[0]["action"] == "timeline.overwrite_clipboard"
    assert three_insert is not None
    assert three_insert.steps[0]["action"] == "timeline.three_point_insert"
    assert three_insert.steps[0]["params"]["target_track_id"] == 1
    assert three_overwrite is not None
    assert three_overwrite.steps[0]["action"] == "timeline.three_point_overwrite"
    assert three_overwrite.steps[0]["params"]["target_track_id"] == 1


def test_ai_action_command_routes_track_state_and_marker_management(tmp_path):
    snapshot = _snapshot(tmp_path)

    lock = build_ai_action_command_plan("lock video track", snapshot)
    unlock = build_ai_action_command_plan("unlock video track", snapshot)
    mute = build_ai_action_command_plan("mute audio track", snapshot)
    rename = build_ai_action_command_plan('rename video track to "B-roll"', snapshot)
    markers = build_ai_action_command_plan("list markers", snapshot)
    snap_off = build_ai_action_command_plan("snap off", snapshot)
    move_marker = build_ai_action_command_plan("move marker to 5s", snapshot)
    next_marker = build_ai_action_command_plan("next marker", snapshot)
    previous_marker = build_ai_action_command_plan("previous marker", snapshot)
    align_playhead = build_ai_action_command_plan("align selected clips to playhead", snapshot)
    align_marker = build_ai_action_command_plan("align selected clips to next marker", snapshot)
    snap_nearest = build_ai_action_command_plan("snap selected clips to nearest", snapshot)
    ripple_delete = build_ai_action_command_plan("ripple delete selected clips", snapshot)
    cleanup_edges = build_ai_action_command_plan("cleanup timeline edges", snapshot)
    list_gaps = build_ai_action_command_plan("list gaps", snapshot)
    close_gap = build_ai_action_command_plan("close gap", snapshot)
    close_all_gaps = build_ai_action_command_plan("close all gaps", snapshot)
    remove_marker = build_ai_action_command_plan("remove marker", snapshot)

    assert lock is not None
    assert lock.steps[0]["action"] == "track.lock"
    assert lock.steps[0]["params"]["locked"] is True
    assert unlock is not None
    assert unlock.steps[0]["action"] == "track.lock"
    assert unlock.steps[0]["params"]["locked"] is False
    assert mute is not None
    assert mute.steps[0]["action"] == "track.mute"
    assert mute.steps[0]["params"]["kind"] == "audio"
    assert mute.steps[0]["params"]["muted"] is True
    assert rename is not None
    assert rename.steps[0]["action"] == "track.rename"
    assert rename.steps[0]["params"]["name"] == "B-roll"
    assert markers is not None
    assert markers.steps[0]["action"] == "timeline.marker.list"
    assert snap_off is not None
    assert snap_off.steps[0]["action"] == "timeline.snap.toggle"
    assert snap_off.steps[0]["params"]["enabled"] is False
    assert move_marker is not None
    assert move_marker.steps[0]["action"] == "timeline.marker.move"
    assert move_marker.steps[0]["params"]["ms"] == 2000
    assert move_marker.steps[0]["params"]["new_ms"] == 5000
    assert next_marker is not None
    assert next_marker.steps[0]["action"] == "timeline.marker.jump"
    assert next_marker.steps[0]["params"]["direction"] == "next"
    assert previous_marker is not None
    assert previous_marker.steps[0]["action"] == "timeline.marker.jump"
    assert previous_marker.steps[0]["params"]["direction"] == "previous"
    assert align_playhead is not None
    assert align_playhead.steps[0]["action"] == "selection.align_to_playhead"
    assert align_marker is not None
    assert align_marker.steps[0]["action"] == "selection.align_to_marker"
    assert align_marker.steps[0]["params"]["direction"] == "next"
    assert snap_nearest is not None
    assert snap_nearest.steps[0]["action"] == "selection.snap_to_nearest"
    assert ripple_delete is not None
    assert ripple_delete.steps[0]["action"] == "selection.ripple_delete"
    assert ripple_delete.steps[0]["params"]["include_linked_audio"] is True
    assert cleanup_edges is not None
    assert cleanup_edges.steps[0]["action"] == "timeline.cleanup_edges"
    assert cleanup_edges.steps[0]["params"]["close_gaps"] is True
    assert list_gaps is not None
    assert list_gaps.steps[0]["action"] == "timeline.gaps"
    assert close_gap is not None
    assert close_gap.steps[0]["action"] == "timeline.close_gap"
    assert close_all_gaps is not None
    assert close_all_gaps.steps[0]["action"] == "timeline.close_all_gaps"
    assert remove_marker is not None
    assert remove_marker.steps[0]["action"] == "timeline.marker.remove"
    assert remove_marker.steps[0]["params"]["ms"] == 2000


def test_ai_action_command_routes_ripple_trim_action(tmp_path):
    snapshot = _snapshot(tmp_path)

    right = build_ai_action_command_plan("ripple trim selected right -200ms", snapshot)
    left = build_ai_action_command_plan("ripple trim selected left 150ms", snapshot)
    to_playhead = build_ai_action_command_plan("trim selected right to playhead", snapshot)

    assert right is not None
    assert right.steps[0]["action"] == "clip.ripple_trim"
    assert right.steps[0]["params"]["edge"] == "right"
    assert right.steps[0]["params"]["delta_ms"] == -200
    assert right.steps[0]["params"]["ripple_linked_audio"] is True
    assert left is not None
    assert left.steps[0]["action"] == "clip.ripple_trim"
    assert left.steps[0]["params"]["edge"] == "left"
    assert left.steps[0]["params"]["delta_ms"] == 150
    assert to_playhead is not None
    assert to_playhead.steps[0]["action"] == "timeline.trim_to_playhead"
    assert to_playhead.steps[0]["params"]["edge"] == "right"
    assert to_playhead.steps[0]["params"]["at_ms"] == 2000


def test_ai_action_command_routes_precision_trim_action(tmp_path):
    snapshot = _snapshot(tmp_path)

    right = build_ai_action_command_plan("precision trim selected right -120ms", snapshot)
    left = build_ai_action_command_plan("exact trim selected left 80ms", snapshot)

    assert right is not None
    assert right.steps[0]["action"] == "timeline.precision_trim"
    assert right.steps[0]["params"]["right_delta_ms"] == -120
    assert right.steps[0]["params"]["ripple"] is False
    assert left is not None
    assert left.steps[0]["action"] == "timeline.precision_trim"
    assert left.steps[0]["params"]["left_delta_ms"] == 80


def test_ai_action_command_does_not_capture_script_or_chat_prompts(tmp_path):
    snapshot = _snapshot(tmp_path)

    assert build_ai_action_command_plan("자막 만들어줘", snapshot) is None
    assert build_ai_action_command_plan("클로드 연결됐어?", snapshot) is None
