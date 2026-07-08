from __future__ import annotations

import json
import os
import sys


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


SRT_SAMPLE = """1
00:00:01,000 --> 00:00:03,000
Um today we explain materials.

2
00:00:04,000 --> 00:00:06,000
어 이제 base color를 연결합니다.
"""


class FakeSettings:
    def __init__(self) -> None:
        self.values = {}
        self.synced = False
        self.set_count = 0

    def value(self, key, default=""):
        return self.values.get(key, default)

    def setValue(self, key, value):
        self.set_count += 1
        self.values[key] = value

    def sync(self):
        self.synced = True


def test_script_edit_model_generates_mvp_plans():
    from app.ai_script_edit_panel import ScriptEditPanelModel

    model = ScriptEditPanelModel(source_media_id="clip_a", language="en")
    document = model.import_transcript_text(SRT_SAMPLE, source_format="srt")
    model.set_silence_intervals([{"start_ms": 3000, "end_ms": 4200}])

    assert document.source_media_id == "clip_a"
    assert len(document.segments) == 2

    captions = model.generate_plan("transcript_to_captions")
    assert captions.operations[0].type == "create_subtitles"
    assert model.preview()["operation_counts"]["create_subtitles"] == 1

    filler = model.generate_plan("remove_filler_words")
    assert all(operation.type == "delete_time_range" for operation in filler.operations)

    silence = model.generate_plan("remove_silences", min_duration_ms=700)
    assert len(silence.operations) == 1
    assert silence.operations[0].start_ms == 3000

    cut = model.generate_plan("text_range_cut", segment_id="seg_001", start_char=0, end_char=2)
    assert cut.operations[0].type == "ripple_cut_text_range"

    clean = model.generate_plan("clean_tutorial")
    shorts = model.generate_plan("shorts")
    product = model.generate_plan("product_demo")
    assert clean.review_cards
    assert any(operation.type == "create_short_candidate" for operation in shorts.operations)
    assert any(operation.type == "add_render_queue_job" for operation in product.operations)


def test_script_edit_selection_resolves_review_cards_to_operations():
    from app.ai_script_edit_panel import ScriptEditPanelModel

    model = ScriptEditPanelModel()
    model.import_transcript_text(SRT_SAMPLE, source_format="srt")
    plan = model.generate_plan("shorts")
    first_card = plan.review_cards[0]

    model.set_selected_operation_ids([])
    model.set_selected_card_ids([first_card.id])

    assert model.selected_operation_ids(include_cards=True) == list(first_card.operation_ids)
    assert model.selected_operation_ids(include_cards=False) == []


def test_script_edit_prompt_routes_to_rule_based_plans():
    from app.ai_script_edit_panel import ScriptEditPanelModel

    model = ScriptEditPanelModel()
    model.import_transcript_text(SRT_SAMPLE, source_format="srt")
    model.set_silence_intervals([{"start_ms": 3000, "end_ms": 4200}])

    clean = model.generate_plan_from_prompt("군더더기 빼고 보기 좋은 자막까지 만들어줘")
    shorts = model.generate_plan_from_prompt("이 영상에서 쇼츠 후보를 만들어줘")
    captions = model.generate_plan_from_prompt("자막만 만들어줘")

    assert clean.intent == "clean_tutorial"
    assert clean.metadata["prompt_mode"] == "local_rule_based"
    assert clean.metadata["local_llm_required"] is False
    assert any(operation.type == "delete_time_range" for operation in clean.operations)
    assert shorts.intent == "shorts"
    assert any(operation.type == "create_short_candidate" for operation in shorts.operations)
    assert captions.intent == "create_subtitles_from_transcript"


def test_script_edit_prompt_understands_zoom_chapter_and_product_language():
    from app.ai_script_edit_panel import ScriptEditPanelModel

    model = ScriptEditPanelModel()
    model.import_transcript_text(SRT_SAMPLE, source_format="srt")

    assert model.resolve_prompt_action("클릭이 잘 보이게 자동줌과 커서 강조 넣어줘") == "clean_tutorial"
    assert model.resolve_prompt_action("챕터 목차 만들고 보기 좋게 정리해줘") == "clean_tutorial"
    assert model.resolve_prompt_action("제품 리뷰 런칭 광고처럼 만들어줘") == "product_demo"


def test_apply_helper_builds_safe_payloads_and_review_intents():
    from app.ai_edit_apply import build_ai_script_apply_payload
    from app.ai_script_edit_panel import ScriptEditPanelModel

    model = ScriptEditPanelModel()
    model.import_transcript_text(SRT_SAMPLE, source_format="srt")
    model.set_silence_intervals([{"start_ms": 3000, "end_ms": 4200}])
    plan = model.generate_plan("clean_tutorial")

    result = build_ai_script_apply_payload(plan)
    payload = result.payload

    assert result.ok is True
    assert payload["subtitle_rows"]
    assert payload["cut_intents"]
    assert payload["sidecars"]
    assert any(warning.startswith("timeline_cut_review_only:") for warning in result.warnings)
    first_sub = payload["subtitle_rows"][0]
    assert first_sub["style"]["preset_id"] == "caption-tutorial-compact"
    assert first_sub["style"]["source"] == "ai_script_edit"
    assert first_sub["style"]["ai_edit_plan_id"] == plan.id


def test_apply_helper_materializes_review_cuts_to_video_and_audio_tracks():
    from app.ai_edit_apply import apply_ai_script_cut_intents_to_tracks
    from app.audio_tracks import AudioClip, AudioTrack
    from app.timeline_model import VideoClip, VideoTrack

    video = VideoTrack(
        id=1,
        clips=[VideoClip(id=10, source_duration_ms=10_000, timeline_in_ms=0, source_in_ms=0, source_out_ms=10_000)],
    )
    audio = AudioTrack(
        id=2,
        clips=[AudioClip(id=20, duration_ms=10_000, offset_ms=0, trim_start_ms=0, trim_end_ms=10_000)],
    )

    result = apply_ai_script_cut_intents_to_tracks(
        [video],
        [audio],
        [
            {"id": "cut_a", "type": "delete_time_range", "start_ms": 2_000, "end_ms": 3_000},
            {"id": "cut_b", "type": "ripple_cut_text_range", "start_ms": 6_000, "end_ms": 7_000},
        ],
    )

    assert result["ok"] is True
    assert result["removed_ms"] == 2_000
    assert len(video.clips) == 3
    assert len(audio.clips) == 3
    assert video.clips[-1].timeline_out_ms == 8_000
    assert audio.clips[-1].offset_ms + audio.clips[-1].effective_length_ms == 8_000
    assert result["applied_ranges"][1]["applied_start_ms"] == 5_000


def test_ai_schema_provider_snapshot_validation_and_log(tmp_path, monkeypatch):
    import app.ai_providers as providers

    monkeypatch.setattr(providers, "_provider_settings", lambda: FakeSettings())
    from app.ai_action_log import append_ai_action_log, read_ai_action_log_tail
    from app.ai_plan_validation import validate_edit_plan_for_snapshot
    from app.ai_project_snapshot import build_project_snapshot_from_editor
    from app.ai_providers import ai_provider_readiness, provider_snapshot, validate_manual_plan_json
    from app.ai_script_edit_panel import ScriptEditPanelModel
    from app.audio_tracks import AudioClip, AudioTrack
    from app.timeline_model import VideoClip, VideoTrack

    class Player:
        def position(self):
            return 1500

    class Editor:
        pass

    editor = Editor()
    editor._tracks = [
        VideoTrack(
            id=1,
            locked=True,
            clips=[VideoClip(id=10, source_duration_ms=10_000, timeline_in_ms=0, source_in_ms=0, source_out_ms=10_000)],
        )
    ]
    editor._audio_tracks = [
        AudioTrack(id=2, clips=[AudioClip(id=20, duration_ms=10_000, offset_ms=0, trim_start_ms=0, trim_end_ms=10_000)])
    ]
    editor._timeline_markers = [{"ms": 1000, "label": "intro"}]
    editor._selected_clips = [(1, 10)]
    editor._player = Player()
    editor._project_settings = {"screenstudio_mode": True}

    snapshot = build_project_snapshot_from_editor(editor)
    assert snapshot["schema_version"] == 1
    assert snapshot["summary"]["video_clip_count"] == 1
    assert snapshot["locks"]["locked_video_track_ids"] == [1]
    assert snapshot["selected_clips"] == [{"track_id": 1, "clip_id": 10}]
    assert snapshot["snapshot_hash"]

    model = ScriptEditPanelModel()
    model.import_transcript_text(SRT_SAMPLE, source_format="srt")
    plan = model.generate_plan("clean_tutorial")
    payload = plan.to_dict()
    assert payload["schema_version"] == 1
    assert payload["provider"] == "rule_based"
    assert validate_manual_plan_json(json.dumps(payload, ensure_ascii=False)).ok is True

    review_validation = validate_edit_plan_for_snapshot(plan, snapshot, destructive_apply=False)
    cut_validation = validate_edit_plan_for_snapshot(plan, snapshot, destructive_apply=True)
    assert review_validation.ok is True
    assert "destructive_operations_are_review_only" in review_validation.warnings
    assert cut_validation.ok is False
    assert any(item.startswith("locked_video_tracks:") for item in cut_validation.blocked)

    readiness = ai_provider_readiness({})
    assert set(readiness) >= {"qwen_local", "rule_based", "local_llm", "codex_mcp", "claude_mcp", "manual_json"}
    assert readiness["qwen_local"]["manifest"]["model_family"] == "Qwen3"
    assert readiness["qwen_local"]["setup_needed"] is True
    providers = provider_snapshot()
    assert providers["cloud_required"] is False
    assert providers["qwen_manifest"]["quantization"] == "Q8_0"
    assert providers["qwen_install_plan"]["model_ref"] == "Qwen/Qwen3-1.7B-GGUF:Q8_0"
    assert "qwen_local" in providers["provider_order"]
    assert providers["automation_mcp"]["registered_commands_only"] is True
    assert "tigercapture_execute_command" in providers["automation_mcp"]["tool_names"]
    assert "tigercapture_execute_action" in providers["automation_mcp"]["tool_names"]
    assert "tigercapture_list_actions" in providers["automation_mcp"]["tool_names"]

    log_path = tmp_path / "ai_action_log.jsonl"
    append_ai_action_log("test_ai_action", {"token": "secret", "plan_id": plan.id}, log_path=log_path)
    tail = read_ai_action_log_tail(log_path)
    assert tail[-1]["action"] == "test_ai_action"
    assert tail[-1]["payload"]["token"] == "<redacted>"


def test_qwen_local_readiness_and_default_provider_fallbacks(tmp_path, monkeypatch):
    import app.ai_providers as providers

    monkeypatch.setattr(providers, "_provider_settings", lambda: FakeSettings())
    from app.ai_providers import ai_provider_readiness, default_ai_provider_id, provider_snapshot

    empty = ai_provider_readiness({})
    qwen = empty["qwen_local"]
    assert qwen["available"] is False
    assert qwen["configured"] is True
    assert qwen["setup_needed"] is True
    assert qwen["setup_state"] == "setup_needed"
    assert "Install default free AI" in qwen["reason"]
    assert default_ai_provider_id({}) == "rule_based"

    model_dir = tmp_path / "qwen"
    model_dir.mkdir()
    qwen_env = {
        "TIGERCAPTURE_QWEN_MODEL_PATH": str(model_dir),
        "TIGERCAPTURE_QWEN_RUNNER_COMMAND": sys.executable,
    }
    ready = ai_provider_readiness(qwen_env)["qwen_local"]
    assert ready["available"] is True
    assert ready["manifest"]["model_size"] == "1.7B"
    assert ready["manifest"]["license"] == "Apache-2.0"
    assert default_ai_provider_id(qwen_env) == "qwen_local"

    requested = dict(qwen_env, TIGERCAPTURE_AI_PROVIDER="rule_based")
    assert default_ai_provider_id(requested) == "rule_based"

    unavailable_requested = dict(qwen_env, TIGERCAPTURE_AI_PROVIDER="local_llm")
    assert default_ai_provider_id(unavailable_requested) == "rule_based"

    endpoint_env = {"TIGERCAPTURE_QWEN_ENDPOINT": "http://127.0.0.1:8000/v1"}
    endpoint_ready = ai_provider_readiness(endpoint_env)["qwen_local"]
    assert endpoint_ready["available"] is True
    assert endpoint_ready["setup_state"] == "endpoint_configured"
    assert endpoint_ready["executor_wired"] is True
    assert "executor can request validated EditPlan JSON" in endpoint_ready["reason"]


def test_qwen_saved_config_and_provider_setup_instructions(monkeypatch, tmp_path):
    import app.ai_providers as providers

    fake_settings = FakeSettings()
    monkeypatch.setattr(providers, "_provider_settings", lambda: fake_settings)
    for key in (
        "TIGERCAPTURE_QWEN_MODEL_PATH",
        "TIGERCAPTURE_QWEN_RUNNER_COMMAND",
        "TIGERCAPTURE_QWEN_ENDPOINT",
    ):
        monkeypatch.delenv(key, raising=False)

    model_dir = tmp_path / "qwen"
    model_dir.mkdir()
    assert providers.save_qwen_provider_config(model_path=str(model_dir), runner_command=sys.executable) is True

    ready = providers.ai_provider_readiness({})["qwen_local"]
    assert ready["available"] is True
    assert ready["model_path"] == str(model_dir)
    assert ready["command"] == sys.executable

    endpoint_ready = providers.ai_provider_readiness({"TIGERCAPTURE_QWEN_ENDPOINT": "http://127.0.0.1:8080/v1"})[
        "qwen_local"
    ]
    assert endpoint_ready["setup_state"] == "endpoint_configured"
    assert endpoint_ready["endpoint"] == "http://127.0.0.1:8080/v1"
    assert endpoint_ready["executor_wired"] is True
    assert providers.provider_state_label(endpoint_ready) == "사용 가능"
    qwen_env = {
        "TIGERCAPTURE_AI_PROVIDER": "qwen_local",
        "TIGERCAPTURE_QWEN_ENDPOINT": "http://127.0.0.1:8080/v1",
    }
    assert providers.effective_generation_provider_id(qwen_env) == "qwen_local"
    assert "무료 AI가 편집 명령을 직접 해석" in providers.provider_status_label(
        qwen_env
    )


def test_qwen_headless_server_helpers(monkeypatch):
    from app.ai_qwen_server import ensure_qwen_server, qwen_models_url, split_runner_command

    assert qwen_models_url("http://127.0.0.1:8080/v1") == "http://127.0.0.1:8080/v1/models"
    assert split_runner_command('llama-server -hf Qwen/Qwen3-1.7B-GGUF:Q8_0')[:2] == ["llama-server", "-hf"]
    assert split_runner_command('"C:\\Tools\\llama.exe" serve -hf Qwen/Qwen3-1.7B-GGUF:Q8_0')[:2] == [
        "C:\\Tools\\llama.exe",
        "serve",
    ]

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, _limit):
            return b'{"data":[]}'

    def alive(_url, timeout=0):
        return FakeResponse()

    started = []

    def fake_popen(*args, **kwargs):
        started.append((args, kwargs))

        class FakeProcess:
            pid = 321

        return FakeProcess()

    already = ensure_qwen_server(endpoint="http://127.0.0.1:8080/v1", command="fake", opener=alive, popen=fake_popen)
    assert already.ok is True
    assert already.already_running is True
    assert not started

    attempts = {"count": 0}

    def becomes_alive(_url, timeout=0):
        attempts["count"] += 1
        if attempts["count"] < 2:
            raise OSError("not ready")
        return FakeResponse()

    launched = ensure_qwen_server(
        endpoint="http://127.0.0.1:8080/v1",
        command="fake-qwen --serve",
        wait_seconds=1,
        poll_seconds=0.1,
        opener=becomes_alive,
        popen=fake_popen,
    )
    assert launched.ok is True
    assert launched.process_started is True
    assert launched.pid == 321
    assert started


def test_qwen_executor_generates_validated_plan(monkeypatch):
    import app.ai_providers as providers
    from app.ai_script_edit_panel import ScriptEditPanelModel

    fake_settings = FakeSettings()
    monkeypatch.setattr(providers, "_provider_settings", lambda: fake_settings)

    model = ScriptEditPanelModel(language="ko")
    model.import_transcript_text(SRT_SAMPLE, source_format="srt", language="ko")
    base_plan = model.generate_plan_from_prompt("자막 만들고 군더더기 제거해줘")
    qwen_plan = base_plan.to_dict()
    qwen_plan["provider"] = "qwen_local"
    qwen_plan["id"] = "qwen_test_plan"
    qwen_plan["summary"] = "무료 AI가 만든 테스트 플랜"

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            payload = {"choices": [{"message": {"content": json.dumps(qwen_plan, ensure_ascii=False)}}]}
            return json.dumps(payload, ensure_ascii=False).encode("utf-8")

    captured = {}

    def fake_urlopen(request, timeout=0):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    import urllib.request

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    result = providers.generate_selected_provider_plan(
        "자막 만들고 군더더기 제거해줘",
        base_plan,
        document=model.document,
        env={
            "TIGERCAPTURE_AI_PROVIDER": "qwen_local",
            "TIGERCAPTURE_QWEN_ENDPOINT": "http://127.0.0.1:8080/v1",
        },
    )

    assert result.ok is True
    assert result.plan is not None
    assert result.plan.provider == "qwen_local"
    assert result.plan.id == "qwen_test_plan"
    assert result.plan.metadata["prompt_mode"] == "qwen_local"
    assert providers.saved_qwen_executor_state()["last_ok"] is True
    assert providers.saved_qwen_executor_state()["last_error"] == ""
    assert captured["url"] == "http://127.0.0.1:8080/v1/chat/completions"
    assert captured["body"]["messages"][0]["role"] == "system"
    assert "safe_baseline_plan" in captured["body"]["messages"][1]["content"]


def test_qwen_executor_repairs_safe_baseline_field_omissions(monkeypatch):
    import app.ai_providers as providers
    from app.ai_script_edit_panel import ScriptEditPanelModel

    fake_settings = FakeSettings()
    monkeypatch.setattr(providers, "_provider_settings", lambda: fake_settings)

    model = ScriptEditPanelModel(language="ko")
    model.import_transcript_text(SRT_SAMPLE, source_format="srt", language="ko")
    base_plan = model.generate_plan_from_prompt("자막 만들고 군더더기 제거해줘")
    qwen_plan = base_plan.to_dict()
    qwen_plan["provider"] = "qwen_local"
    qwen_plan["summary"] = "로컬 AI가 baseline을 보정한 플랜"
    first_op = qwen_plan["operations"][0]
    first_op.pop("type", None)
    first_op["confidence"] = 80

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            payload = {"choices": [{"message": {"content": json.dumps(qwen_plan, ensure_ascii=False)}}]}
            return json.dumps(payload, ensure_ascii=False).encode("utf-8")

    import urllib.request

    monkeypatch.setattr(urllib.request, "urlopen", lambda *_args, **_kwargs: FakeResponse())
    result = providers.generate_selected_provider_plan(
        "자막 만들고 군더더기 제거해줘",
        base_plan,
        document=model.document,
        env={
            "TIGERCAPTURE_AI_PROVIDER": "qwen_local",
            "TIGERCAPTURE_QWEN_ENDPOINT": "http://127.0.0.1:8080/v1",
        },
    )

    assert result.ok is True
    assert result.plan is not None
    assert result.plan.operations[0].type == base_plan.operations[0].type
    assert result.plan.operations[0].confidence is None
    assert "op[0].type" in result.plan.metadata["provider_repair_notes"]
    assert "op[0].confidence" in result.plan.metadata["provider_repair_notes"]


def test_qwen_executor_falls_back_on_bad_response(monkeypatch):
    import app.ai_providers as providers
    from app.ai_script_edit_panel import ScriptEditPanelModel

    fake_settings = FakeSettings()
    monkeypatch.setattr(providers, "_provider_settings", lambda: fake_settings)
    model = ScriptEditPanelModel(language="ko")
    model.import_transcript_text(SRT_SAMPLE, source_format="srt", language="ko")
    base_plan = model.generate_plan_from_prompt("쇼츠로 만들어줘")

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({"choices": [{"message": {"content": "좋아요, 제가 처리할게요."}}]}).encode("utf-8")

    import urllib.request

    monkeypatch.setattr(urllib.request, "urlopen", lambda *_args, **_kwargs: FakeResponse())
    result = providers.generate_selected_provider_plan(
        "쇼츠로 만들어줘",
        base_plan,
        document=model.document,
        env={
            "TIGERCAPTURE_AI_PROVIDER": "qwen_local",
            "TIGERCAPTURE_QWEN_ENDPOINT": "http://127.0.0.1:8080/v1",
        },
    )
    assert result.ok is False
    assert "기본 자동 규칙" in result.reason


def test_qwen_executor_hides_connection_refused_technical_error(monkeypatch):
    import urllib.error

    import app.ai_providers as providers
    from app.ai_script_edit_panel import ScriptEditPanelModel

    fake_settings = FakeSettings()
    monkeypatch.setattr(providers, "_provider_settings", lambda: fake_settings)
    model = ScriptEditPanelModel(language="ko")
    model.import_transcript_text(SRT_SAMPLE, source_format="srt", language="ko")
    base_plan = model.generate_plan_from_prompt("미디어 풀 동영상을 배치해줘")

    import urllib.request

    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            urllib.error.URLError(ConnectionRefusedError(10061, "connection refused"))
        ),
    )
    result = providers.generate_selected_provider_plan(
        "미디어 풀 동영상을 배치해줘",
        base_plan,
        document=model.document,
        env={
            "TIGERCAPTURE_AI_PROVIDER": "qwen_local",
            "TIGERCAPTURE_QWEN_ENDPOINT": "http://127.0.0.1:8080/v1",
        },
    )

    assert result.ok is False
    assert "무료 AI 서버가 꺼져 있거나 응답하지 않아" in result.reason
    assert "WinError" not in result.reason
    assert "urlopen" not in result.reason
    ready = providers.ai_provider_readiness({"TIGERCAPTURE_QWEN_ENDPOINT": "http://127.0.0.1:8080/v1"})[
        "qwen_local"
    ]
    assert ready["setup_state"] == "executor_failed"
    assert providers.provider_state_label(ready) == "확인 필요"
    assert "마지막 호출이 실패" in providers.provider_status_label(
        {
            "TIGERCAPTURE_AI_PROVIDER": "qwen_local",
            "TIGERCAPTURE_QWEN_ENDPOINT": "http://127.0.0.1:8080/v1",
        }
    )

    qwen_help = providers.provider_setup_instructions("qwen_local")
    assert "llama.cpp" in qwen_help["body"]
    assert "Qwen/Qwen3-1.7B-GGUF:Q8_0" in qwen_help["server_command"]

    codex_help = providers.provider_setup_instructions("codex_mcp")
    assert "TIGERCAPTURE_CODEX_MCP_ENABLED" in codex_help["body"]
    assert "automation_mcp_server.py" in codex_help["server_command"]

    claude_help = providers.provider_setup_instructions("claude_mcp")
    assert "claude mcp add" in claude_help["claude_command"]
    assert "Claude Code 터미널 열기" in claude_help["primary_action"]
    assert "automation_mcp_server.py" in claude_help["server_command"]


def test_ai_provider_status_prompt_is_not_an_edit_prompt():
    import app.ai_providers as providers

    assert providers.is_ai_provider_status_prompt("클로드 연결됐어?", "claude_mcp") is True
    assert providers.is_ai_provider_status_prompt("Claude connected?", "claude_mcp") is True
    assert providers.is_ai_provider_status_prompt("로컬 LLM 상태 알려줘", "local_llm") is True
    assert providers.is_ai_provider_status_prompt("클로드로 자막 만들어줘", "claude_mcp") is False
    assert providers.is_ai_provider_status_prompt("미디어 풀의 동영상을 배치해줘", "claude_mcp") is False


def test_ai_provider_interaction_model_separates_terminal_and_review_modes():
    import app.ai_providers as providers

    claude = providers.provider_interaction_model(
        "claude_mcp",
        {"id": "claude_mcp", "available": True, "executor_wired": True},
    )
    local_missing = providers.provider_interaction_model(
        "local_llm",
        {"id": "local_llm", "available": False, "executor_wired": False},
    )
    local_ready = providers.provider_interaction_model(
        "local_llm",
        {"id": "local_llm", "available": True, "executor_wired": True},
    )

    assert claude["surface"] == "terminal_handoff"
    assert claude["run_label"] == "Claude CLI 열기"
    assert claude["opens_terminal"] is True
    assert "Review" in claude["summary"]
    assert local_missing["run_label"] == "로컬 LLM 설정"
    assert local_ready["run_label"] == "로컬 LLM 실행"
    assert local_ready["can_direct_generate"] is True


def test_ai_provider_user_state_makes_fallback_explicit(monkeypatch):
    import app.ai_providers as providers

    fake_settings = FakeSettings()
    monkeypatch.setattr(providers, "_provider_settings", lambda: fake_settings)
    monkeypatch.setattr(providers, "_find_claude_cli_command", lambda _env=None: sys.executable)
    assert providers.save_claude_mcp_config(enabled=True, command=sys.executable, cli_command=sys.executable)

    claude = providers.provider_user_state(provider_id="claude_mcp")
    assert claude["selected_provider"] == "claude_mcp"
    assert claude["effective_generation_provider"] == "claude_mcp"
    assert claude["uses_rule_fallback"] is False
    assert claude["direct_ai"] is True
    assert claude["opens_terminal"] is False

    claude = providers.provider_user_state(
        {"TIGERCAPTURE_CLAUDE_DIRECT_EXECUTOR": "0"},
        provider_id="claude_mcp",
    )
    assert claude["selected_provider"] == "claude_mcp"
    assert claude["effective_generation_provider"] == "rule_based"
    assert claude["uses_rule_fallback"] is True
    assert claude["opens_terminal"] is True
    assert "직접 생성" in claude["headline"]

    qwen_missing = providers.provider_user_state(provider_id="qwen_local")
    assert qwen_missing["uses_rule_fallback"] is True
    assert "기본 무료 AI" in qwen_missing["headline"]
    assert qwen_missing["action_label"] == "무료 AI 설치"

    local_env = {"TIGERCAPTURE_LOCAL_LLM_COMMAND": sys.executable}
    local_ready = providers.provider_user_state(local_env, provider_id="local_llm")
    assert local_ready["effective_generation_provider"] == "local_llm"
    assert local_ready["direct_ai"] is True
    assert local_ready["uses_rule_fallback"] is False


def test_saved_local_llm_config_enables_executor_without_env(monkeypatch):
    import app.ai_providers as providers

    fake_settings = FakeSettings()
    monkeypatch.setattr(providers, "_provider_settings", lambda: fake_settings)
    monkeypatch.delenv("TIGERCAPTURE_LOCAL_LLM_COMMAND", raising=False)

    assert providers.saved_local_llm_config() == {"command": ""}
    assert providers.save_local_llm_provider_config(command=sys.executable) is True
    assert providers.saved_local_llm_config()["command"] == sys.executable

    ready = providers.ai_provider_readiness({})["local_llm"]
    interaction = providers.provider_interaction_model("local_llm", ready)

    assert ready["available"] is True
    assert ready["configured"] is True
    assert ready["command"] == sys.executable
    assert ready["executor_wired"] is True
    assert interaction["can_direct_generate"] is True


def test_saved_claude_mcp_config_enables_readiness(monkeypatch):
    import app.ai_providers as providers

    fake_settings = FakeSettings()
    monkeypatch.setattr(providers, "_provider_settings", lambda: fake_settings)
    monkeypatch.setattr(providers, "_find_claude_cli_command", lambda _env=None: "")
    monkeypatch.delenv("TIGERCAPTURE_CLAUDE_MCP_ENABLED", raising=False)
    monkeypatch.delenv("TIGERCAPTURE_CLAUDE_MCP_COMMAND", raising=False)

    assert providers.saved_claude_mcp_config() == {"enabled": False, "command": ""}
    assert providers.save_claude_mcp_config(enabled=True, command=sys.executable) is True
    assert providers.saved_claude_mcp_config()["enabled"] is True

    ready = providers.ai_provider_readiness({"TIGERCAPTURE_CLAUDE_DIRECT_EXECUTOR": "0"})["claude_mcp"]
    assert ready["configured"] is True
    assert ready["available"] is True
    assert ready["command"] == sys.executable
    assert ready["executor_wired"] is False
    assert providers.provider_state_label(ready) == "MCP 등록됨"
    assert "Claude MCP가 등록" in providers.provider_status_label({"TIGERCAPTURE_AI_PROVIDER": "claude_mcp"})

    monkeypatch.setattr(providers, "_find_claude_cli_command", lambda _env=None: sys.executable)
    ready_with_cli = providers.ai_provider_readiness({})["claude_mcp"]
    assert ready_with_cli["executor_wired"] is True
    assert ready_with_cli["direct_generation_enabled"] is True
    assert ready_with_cli["cli_command"] == sys.executable
    assert ready_with_cli["generation_fallback_provider"] == ""
    ready_with_cli["direct_generation_enabled"] = False
    assert providers.provider_state_label(ready_with_cli) == "터미널 가능"
    assert "Claude 직접 Plan 생성 가능" in providers.provider_status_label(
        {"TIGERCAPTURE_AI_PROVIDER": "claude_mcp"}
    )

    direct_env = {
        "TIGERCAPTURE_AI_PROVIDER": "claude_mcp",
        "TIGERCAPTURE_CLAUDE_DIRECT_EXECUTOR": "1",
    }
    direct_ready = providers.ai_provider_readiness(direct_env)["claude_mcp"]
    assert direct_ready["direct_generation_enabled"] is True
    assert direct_ready["generation_fallback_provider"] == ""
    disabled_ready = providers.ai_provider_readiness({"TIGERCAPTURE_CLAUDE_DIRECT_EXECUTOR": "0"})["claude_mcp"]
    assert disabled_ready["direct_generation_enabled"] is False
    assert disabled_ready["generation_fallback_provider"] == "rule_based"
    assert providers.provider_state_label(direct_ready) == "직접 생성 가능"


def test_claude_executor_failure_marks_provider_as_needing_attention(monkeypatch):
    import app.ai_providers as providers

    fake_settings = FakeSettings()
    monkeypatch.setattr(providers, "_provider_settings", lambda: fake_settings)
    monkeypatch.setattr(providers, "_find_claude_cli_command", lambda _env=None: sys.executable)
    assert providers.save_claude_mcp_config(enabled=True, command=sys.executable, cli_command=sys.executable) is True
    assert providers.save_claude_executor_state(ok=False, error="Claude 로그인 필요") is True

    ready = providers.ai_provider_readiness({"TIGERCAPTURE_CLAUDE_DIRECT_EXECUTOR": "0"})["claude_mcp"]

    assert ready["available"] is True
    assert ready["executor_wired"] is True
    assert ready["setup_state"] == "ready"
    assert ready["direct_generation_enabled"] is False
    assert ready["generation_fallback_provider"] == "rule_based"
    assert providers.provider_state_label(ready) == "터미널 가능"

    direct_env = {
        "TIGERCAPTURE_AI_PROVIDER": "claude_mcp",
        "TIGERCAPTURE_CLAUDE_DIRECT_EXECUTOR": "1",
    }
    ready = providers.ai_provider_readiness(direct_env)["claude_mcp"]

    assert ready["setup_state"] == "executor_failed"
    assert ready["direct_generation_enabled"] is True
    assert ready["generation_fallback_provider"] == "rule_based"
    assert providers.provider_state_label(ready) == "확인 필요"
    assert "마지막 앱 내부 호출이 실패" in providers.provider_status_label(
        direct_env
    )


def test_script_edit_panel_provider_copy_shows_claude_direct_mode(monkeypatch):
    from PySide6.QtWidgets import QApplication

    import app.ai_providers as providers
    from app.ai_script_edit_panel import ScriptEditPanel

    fake_settings = FakeSettings()
    monkeypatch.setattr(providers, "_provider_settings", lambda: fake_settings)
    monkeypatch.setattr(providers, "_find_claude_cli_command", lambda _env=None: sys.executable)
    assert providers.save_claude_mcp_config(enabled=True, command=sys.executable, cli_command=sys.executable)
    assert providers.save_ai_provider_preference("claude_mcp")

    app = QApplication.instance() or QApplication([])
    panel = ScriptEditPanel()

    assert app is not None
    assert panel._provider_combo.currentData() == "claude_mcp"
    assert panel._prompt_btn.text() == "Plan 생성"
    assert "직접 생성" in panel._provider_detail_label.text()
    assert "Claude Code" in panel._prompt_input.placeholderText()


def test_script_edit_panel_review_mode_hides_entry_tools():
    from PySide6.QtWidgets import QApplication

    from app.ai_script_edit_panel import ScriptEditPanel

    app = QApplication.instance() or QApplication([])
    panel = ScriptEditPanel()

    assert app is not None
    assert panel._prompt_input.isHidden() is False
    assert panel._transcript_input.isHidden() is False

    panel.set_review_mode(True)

    assert panel._prompt_input.isHidden() is True
    assert panel._transcript_tools_host.isHidden() is True
    assert panel._transcript_input.isHidden() is True
    assert panel._segments_list.isHidden() is True
    assert panel._manual_controls_host.isHidden() is True
    assert panel._manual_generate_host.isHidden() is True
    assert panel._summary_label.isHidden() is False
    assert panel._cards_list.isHidden() is False
    assert panel._operations_list.isHidden() is False
    assert panel._review_hint_label.isHidden() is False

    panel.set_review_mode(False)
    assert panel._prompt_input.isHidden() is False
    assert panel._transcript_input.isHidden() is False


def test_script_edit_review_mode_keeps_prompt_only_requests_out_of_transcript():
    from PySide6.QtWidgets import QApplication

    from app.ai_edit_plan import EditPlan
    from app.ai_script_edit_panel import ScriptEditPanel

    app = QApplication.instance() or QApplication([])
    panel = ScriptEditPanel()
    panel._transcript_input.setPlainText(SRT_SAMPLE)
    panel.import_transcript_from_text()

    assert app is not None
    assert panel.model.document is not None
    assert panel._segments_list.count() > 0

    panel.clear_transcript_context(clear_plan=False)
    plan = EditPlan(
        id="prompt_only",
        intent="prompt_only_edit_request",
        summary="AI 명령 검토 대기: 클로드 연결됐어?",
        operations=(),
        warnings=("provider status only",),
        quality_score=45,
        metadata={
            "prompt_text": "클로드 연결됐어?",
            "prompt_mode": "command_only",
            "transcript_required": False,
        },
    )
    panel.set_review_mode(True)
    panel.set_plan(plan)

    assert panel.model.document is None
    assert panel._transcript_input.toPlainText() == ""
    assert panel._segments_list.count() == 0
    assert "자막 입력창이 아니라" in panel._review_hint_label.text()
    assert "자막으로 변환되지" in panel._summary_label.text()


def test_script_edit_status_prompt_does_not_import_prompt_as_transcript(monkeypatch):
    from PySide6.QtWidgets import QApplication

    import app.ai_providers as providers
    from app.ai_script_edit_panel import ScriptEditPanel

    fake_settings = FakeSettings()
    monkeypatch.setattr(providers, "_provider_settings", lambda: fake_settings)
    monkeypatch.setattr(providers, "_find_claude_cli_command", lambda _env=None: sys.executable)
    assert providers.save_claude_mcp_config(enabled=True, command=sys.executable, cli_command=sys.executable)
    assert providers.save_ai_provider_preference("claude_mcp")

    app = QApplication.instance() or QApplication([])
    panel = ScriptEditPanel()
    panel._prompt_input.setPlainText("클로드 연결됐어?")
    plan = panel.generate_from_prompt()

    assert app is not None
    assert plan.intent == "prompt_only_edit_request"
    assert plan.operations == ()
    assert plan.metadata["transcript_required"] is False
    assert panel.model.document is None
    assert panel._segments_list.count() == 0
    assert "자막으로 변환되지" in panel._summary_label.text()


def test_claude_print_invocation_does_not_send_empty_tools(monkeypatch):
    import subprocess

    import app.ai_providers as providers

    captured = {}

    class Completed:
        returncode = 0
        stdout = '{"type":"result","result":"{}"}'
        stderr = ""

    def fake_run(args, **kwargs):
        captured["args"] = list(args)
        captured["kwargs"] = dict(kwargs)
        return Completed()

    monkeypatch.setattr(subprocess, "run", fake_run)

    output = providers._run_claude_cli_print(sys.executable, "hello", timeout_seconds=5)

    assert output == Completed.stdout
    assert "--print" in captured["args"]
    assert "--tools" not in captured["args"]
    assert "--input-format" in captured["args"]
    assert captured["kwargs"]["input"] == "hello"
    assert captured["args"][-1] != "hello"


def test_claude_executor_generates_validated_plan(monkeypatch):
    import app.ai_providers as providers
    from app.ai_script_edit_panel import ScriptEditPanelModel

    fake_settings = FakeSettings()
    monkeypatch.setattr(providers, "_provider_settings", lambda: fake_settings)
    monkeypatch.setattr(providers, "_find_claude_cli_command", lambda _env=None: sys.executable)
    assert providers.save_claude_mcp_config(enabled=True, command=sys.executable, cli_command=sys.executable) is True

    model = ScriptEditPanelModel(language="ko")
    model.import_transcript_text(SRT_SAMPLE, source_format="srt", language="ko")
    base_plan = model.generate_plan_from_prompt("군더더기 제거하고 자막")
    plan_dict = base_plan.to_dict()
    plan_dict["provider"] = "claude_mcp"
    plan_dict["summary"] = "Claude generated safe plan"
    plan_dict["metadata"] = {"source": "test"}
    wrapper = {"type": "result", "result": json.dumps(plan_dict, ensure_ascii=False)}
    monkeypatch.setattr(
        providers,
        "_run_claude_cli_print",
        lambda *_args, **_kwargs: json.dumps(wrapper, ensure_ascii=False),
    )

    result = providers.generate_selected_provider_plan(
        "군더더기 제거하고 자막",
        base_plan,
        document=model.document,
        env={
            "TIGERCAPTURE_AI_PROVIDER": "claude_mcp",
        },
    )

    assert result.ok is True
    assert result.provider == "claude_mcp"
    assert result.plan is not None
    assert result.plan.provider == "claude_mcp"
    assert result.plan.metadata["provider_executor"] == "claude_cli_print"


def test_provider_plan_repairs_missing_review_card_ids_before_validation():
    import app.ai_providers as providers
    from app.ai_script_edit_panel import ScriptEditPanelModel

    model = ScriptEditPanelModel(language="ko")
    model.import_transcript_text(SRT_SAMPLE, source_format="srt", language="ko")
    base_plan = model.generate_plan_from_prompt("군더더기 제거하고 자막")
    payload = base_plan.to_dict()
    for operation in payload["operations"]:
        operation.pop("id", None)
    payload["review_cards"] = [
        {
            "title": "검토",
            "operation_ids": [],
            "quality_score": 80,
        }
    ]

    result = providers.validate_provider_plan_json("claude_mcp", json.dumps(payload, ensure_ascii=False))

    assert result.ok is True
    assert result.plan is not None
    assert result.plan.provider == "claude_mcp"
    assert result.plan.review_cards[0].id == "card_001"
    assert set(result.plan.review_cards[0].operation_ids) == {operation.id for operation in result.plan.operations}
    assert set(result.metadata["provider_repairs"]) >= {
        "operation_ids",
        "review_card_ids",
        "review_card_operation_ids",
    }


def test_local_llm_executor_generates_validated_plan(monkeypatch):
    import app.ai_providers as providers
    from app.ai_script_edit_panel import ScriptEditPanelModel

    fake_settings = FakeSettings()
    monkeypatch.setattr(providers, "_provider_settings", lambda: fake_settings)

    model = ScriptEditPanelModel(language="ko")
    model.import_transcript_text(SRT_SAMPLE, source_format="srt", language="ko")
    base_plan = model.generate_plan_from_prompt("자막 만들고 쇼츠 후보")
    plan_dict = base_plan.to_dict()
    plan_dict["provider"] = "local_llm"
    plan_dict["summary"] = "Local LLM generated safe plan"
    plan_dict["metadata"] = {"source": "test"}
    wrapper = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(plan_dict, ensure_ascii=False),
                }
            }
        ]
    }
    monkeypatch.setattr(
        providers,
        "_run_local_llm_command",
        lambda *_args, **_kwargs: json.dumps(wrapper, ensure_ascii=False),
    )

    env = {
        "TIGERCAPTURE_AI_PROVIDER": "local_llm",
        "TIGERCAPTURE_LOCAL_LLM_COMMAND": sys.executable,
    }
    ready = providers.ai_provider_readiness(env)["local_llm"]
    assert ready["available"] is True
    assert ready["executor_wired"] is True
    assert providers.provider_state_label(ready) == "사용 가능"
    assert "로컬 LLM 실행 가능" in providers.provider_status_label(env)

    result = providers.generate_selected_provider_plan(
        "자막 만들고 쇼츠 후보",
        base_plan,
        document=model.document,
        env=env,
    )

    assert result.ok is True
    assert result.provider == "local_llm"
    assert result.plan is not None
    assert result.plan.provider == "local_llm"
    assert result.plan.metadata["provider_executor"] == "local_llm_command"


def test_codex_executor_generates_validated_plan(monkeypatch):
    import app.ai_providers as providers
    from app.ai_script_edit_panel import ScriptEditPanelModel

    fake_settings = FakeSettings()
    monkeypatch.setattr(providers, "_provider_settings", lambda: fake_settings)

    model = ScriptEditPanelModel(language="ko")
    model.import_transcript_text(SRT_SAMPLE, source_format="srt", language="ko")
    base_plan = model.generate_plan_from_prompt("튜토리얼을 숏폼으로 정리해줘")
    plan_dict = base_plan.to_dict()
    plan_dict["provider"] = "codex_mcp"
    plan_dict["summary"] = "Codex generated safe plan"
    plan_dict["metadata"] = {"source": "test"}
    wrapper = {"result": json.dumps(plan_dict, ensure_ascii=False)}

    captured = {}

    def fake_run_command(command, payload, **_kwargs):
        captured["command"] = command
        captured["payload"] = payload
        return json.dumps(wrapper, ensure_ascii=False)

    monkeypatch.setattr(providers, "_run_local_llm_command", fake_run_command)

    env = {
        "TIGERCAPTURE_AI_PROVIDER": "codex_mcp",
        "TIGERCAPTURE_CODEX_EXECUTOR_COMMAND": sys.executable,
    }
    ready = providers.ai_provider_readiness(env)["codex_mcp"]
    assert ready["available"] is True
    assert ready["executor_wired"] is True
    assert providers.effective_generation_provider_id(env) == "codex_mcp"

    result = providers.generate_selected_provider_plan(
        "튜토리얼을 숏폼으로 정리해줘",
        base_plan,
        document=model.document,
        env=env,
    )

    assert result.ok is True
    assert result.provider == "codex_mcp"
    assert result.plan is not None
    assert result.plan.provider == "codex_mcp"
    assert result.plan.metadata["provider_executor"] == "codex_executor_command"
    assert captured["payload"]["task"] == "tiger_studio_codex_edit_plan"
    assert "safe_baseline_plan" in captured["payload"]


def test_provider_selection_prefers_env_then_saved_then_default(monkeypatch, tmp_path):
    import app.ai_providers as providers

    fake_settings = FakeSettings()
    monkeypatch.setattr(providers, "_provider_settings", lambda: fake_settings)

    assert providers.save_ai_provider_preference("claude_mcp") is True
    assert fake_settings.synced is True
    assert providers.saved_ai_provider_id() == "claude_mcp"
    assert providers.selected_ai_provider_id({}) == "claude_mcp"
    assert providers.effective_generation_provider_id({}) == "rule_based"
    assert "Claude 연결이 설정되지 않아" in providers.provider_status_label({})

    model_dir = tmp_path / "qwen"
    model_dir.mkdir()
    env = {
        "TIGERCAPTURE_AI_PROVIDER": "qwen_local",
        "TIGERCAPTURE_QWEN_MODEL_PATH": str(model_dir),
        "TIGERCAPTURE_QWEN_RUNNER_COMMAND": sys.executable,
    }
    assert providers.selected_ai_provider_id(env) == "qwen_local"
    assert providers.default_ai_provider_id(env) == "qwen_local"
    assert providers.effective_generation_provider_id(env) == "rule_based"
    snapshot = providers.provider_snapshot(env)
    assert snapshot["selected_provider"] == "qwen_local"
    assert snapshot["effective_generation_provider"] == "rule_based"
    assert "OpenAI-compatible endpoint" in snapshot["fallback_reason"]


def test_script_edit_provider_refresh_does_not_write_preference(monkeypatch):
    from PySide6.QtWidgets import QApplication

    import app.ai_providers as providers
    from app.ai_script_edit_panel import ScriptEditPanel

    fake_settings = FakeSettings()
    monkeypatch.setattr(providers, "_provider_settings", lambda: fake_settings)
    for key in (
        "TIGERCAPTURE_AI_PROVIDER",
        "TIGERCAPTURE_QWEN_MODEL_PATH",
        "TIGERCAPTURE_QWEN_RUNNER_COMMAND",
        "TIGERCAPTURE_QWEN_ENDPOINT",
        "TIGERCAPTURE_LOCAL_LLM_COMMAND",
        "TIGERCAPTURE_CODEX_MCP_ENABLED",
        "TIGERCAPTURE_CLAUDE_MCP_ENABLED",
    ):
        monkeypatch.delenv(key, raising=False)

    app = QApplication.instance() or QApplication([])
    panel = ScriptEditPanel()

    assert app is not None
    assert fake_settings.values == {}
    assert fake_settings.set_count == 0

    panel._refresh_provider_status()

    assert fake_settings.values == {}
    assert fake_settings.set_count == 0
    qwen_idx = panel._provider_combo.findData("qwen_local")
    assert qwen_idx >= 0
    panel._provider_combo.setCurrentIndex(qwen_idx)
    assert fake_settings.values["ai/provider"] == "qwen_local"
    assert fake_settings.set_count == 1


def test_script_edit_panel_local_llm_setup_saves_command(monkeypatch):
    from PySide6.QtWidgets import QApplication

    import app.ai_providers as providers
    import app.ai_script_edit_panel as panel_module
    from app.ai_script_edit_panel import ScriptEditPanel

    fake_settings = FakeSettings()
    monkeypatch.setattr(providers, "_provider_settings", lambda: fake_settings)
    monkeypatch.delenv("TIGERCAPTURE_LOCAL_LLM_COMMAND", raising=False)
    monkeypatch.setattr(panel_module.QInputDialog, "getText", lambda *args, **kwargs: (sys.executable, True))
    monkeypatch.setattr(panel_module.QMessageBox, "information", lambda *args, **kwargs: 0)
    monkeypatch.setattr(panel_module.QMessageBox, "warning", lambda *args, **kwargs: 0)

    app = QApplication.instance() or QApplication([])
    panel = ScriptEditPanel()
    idx = panel._provider_combo.findData("local_llm")
    assert idx >= 0
    panel._provider_combo.setCurrentIndex(idx)

    assert app is not None
    assert panel._show_local_llm_setup_dialog() is True
    assert providers.saved_local_llm_config()["command"] == sys.executable
    assert providers.ai_provider_readiness({})["local_llm"]["available"] is True
    assert fake_settings.values["ai/provider"] == "local_llm"


def test_script_edit_panel_provider_setup_can_delegate_to_editor(monkeypatch):
    from PySide6.QtWidgets import QApplication

    import app.ai_providers as providers
    import app.ai_script_edit_panel as panel_module
    from app.ai_script_edit_panel import ScriptEditPanel

    fake_settings = FakeSettings()
    monkeypatch.setattr(providers, "_provider_settings", lambda: fake_settings)
    monkeypatch.setattr(panel_module.QMessageBox, "exec", lambda self: 0)

    app = QApplication.instance() or QApplication([])
    panel = ScriptEditPanel()
    calls = []
    emitted = []
    panel.set_external_provider_setup_handler(lambda provider_id: calls.append(provider_id))
    panel.provider_setup_requested.connect(lambda provider_id: emitted.append(provider_id))

    idx = panel._provider_combo.findData("qwen_local")
    assert idx >= 0
    panel._provider_combo.setCurrentIndex(idx)
    panel._show_provider_setup_dialog()

    assert app is not None
    assert calls == ["qwen_local"]
    assert emitted == ["qwen_local"]


def test_validate_provider_plan_json_attaches_provider_and_rejects_bad_output():
    from app.ai_providers import validate_provider_plan_json
    from app.ai_script_edit_panel import ScriptEditPanelModel

    model = ScriptEditPanelModel()
    model.import_transcript_text(SRT_SAMPLE, source_format="srt")
    plan = model.generate_plan("clean_tutorial")
    valid = validate_provider_plan_json("qwen_local", json.dumps(plan.to_dict(), ensure_ascii=False))

    assert valid.ok is True
    assert valid.provider == "qwen_local"
    assert valid.plan is not None
    assert valid.plan.provider == "qwen_local"
    assert valid.metadata["validated_provider"] == "qwen_local"

    malformed = validate_provider_plan_json("qwen_local", "{not json")
    assert malformed.ok is False
    assert malformed.provider == "qwen_local"

    payload = plan.to_dict()
    payload.setdefault("metadata", {})["command"] = "delete everything"
    forbidden = validate_provider_plan_json("qwen_local", json.dumps(payload, ensure_ascii=False))
    assert forbidden.ok is False
    assert "not allowed" in forbidden.reason.casefold()


def test_provider_snapshot_exposes_selection_order_and_qwen_manifest(tmp_path):
    from app.ai_providers import provider_snapshot

    model_dir = tmp_path / "qwen"
    model_dir.mkdir()
    env = {
        "TIGERCAPTURE_AI_PROVIDER": "qwen_local",
        "TIGERCAPTURE_QWEN_MODEL_PATH": str(model_dir),
        "TIGERCAPTURE_QWEN_RUNNER_COMMAND": sys.executable,
    }

    snapshot = provider_snapshot(env)

    assert snapshot["selected_provider"] == "qwen_local"
    assert snapshot["default_provider"] == "qwen_local"
    assert snapshot["provider_order"][0] == "qwen_local"
    assert snapshot["qwen_manifest"] == snapshot["providers"]["qwen_local"]["manifest"]
    assert snapshot["qwen_manifest"]["mode"] == "local_bundled_optional_download"


def test_qwen_local_process_shutdown_terminates_tracked_qprocess():
    from PySide6.QtCore import QProcess

    from app.video_editor_window import VideoEditorWindow

    class FakeProcess:
        def __init__(self) -> None:
            self.terminated = False
            self.killed = False
            self.wait_timeouts = []

        def state(self):
            return QProcess.ProcessState.Running

        def terminate(self) -> None:
            self.terminated = True

        def kill(self) -> None:
            self.killed = True

        def waitForFinished(self, timeout: int) -> bool:
            self.wait_timeouts.append(timeout)
            return self.killed

    process = FakeProcess()
    logs = []
    editor = VideoEditorWindow.__new__(VideoEditorWindow)
    editor._qwen_install_process = process
    editor._qwen_server_process = process
    editor._qwen_install_log = logs.append

    VideoEditorWindow._shutdown_qwen_local_processes(editor, reason="unit_test", timeout_ms=1)

    assert process.terminated is True
    assert process.killed is True
    assert process.wait_timeouts == [100, 500]
    assert editor._qwen_install_process is None
    assert editor._qwen_server_process is None
    assert logs == ["Qwen local process shutdown: unit_test"]


def test_apply_helper_short_candidates_and_render_jobs_are_sidecar_safe():
    from app.ai_edit_apply import build_ai_script_apply_payload
    from app.ai_script_edit_panel import ScriptEditPanelModel

    model = ScriptEditPanelModel()
    model.import_transcript_text(SRT_SAMPLE, source_format="srt")
    plan = model.generate_plan("shorts")

    result = build_ai_script_apply_payload(plan)
    payload = result.payload

    assert payload["timeline_markers"]
    assert payload["short_candidates"]
    assert payload["render_queue_jobs"]
    assert any(warning.startswith("render_queue_job_sidecar_only:") for warning in result.warnings)
    assert payload["render_queue_jobs"][0]["source"] == "ai_script_edit"


def test_script_edit_panel_local_stt_missing_is_non_fatal(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication

    from app.ai_script_edit_panel import ScriptEditPanel

    app = QApplication.instance() or QApplication([])
    media = tmp_path / "sample.wav"
    media.write_bytes(b"not a real wav")

    def fake_transcribe(path, *, language=""):
        return {
            "ok": False,
            "available": False,
            "segments": [],
            "reason": "local_whisper_model_missing",
            "actions": ["Set TIGERCAPTURE_LOCAL_WHISPER_MODEL."],
        }

    monkeypatch.setattr("app.local_ml.local_ml_transcribe_media", fake_transcribe)
    panel = ScriptEditPanel()

    assert app is not None
    assert panel.import_transcript_from_media_path(media) is None
    assert "local_whisper_model_missing" in panel._prompt_mode_label.text()


def test_apply_helper_adapter_uses_explicit_safe_methods_only():
    from app.ai_edit_apply import apply_ai_script_plan_to_adapter
    from app.ai_script_edit_panel import ScriptEditPanelModel

    class Adapter:
        def __init__(self) -> None:
            self.subtitles = []
            self.markers = []
            self.cuts = []
            self.sidecar = None

        def add_subtitle_rows(self, rows):
            self.subtitles.extend(rows)
            return len(rows)

        def add_timeline_markers(self, rows):
            self.markers.extend(rows)
            return len(rows)

        def stage_cut_intents(self, rows):
            self.cuts.extend(rows)
            return len(rows)

        def store_ai_script_sidecar(self, payload):
            self.sidecar = payload

    model = ScriptEditPanelModel()
    model.import_transcript_text(SRT_SAMPLE, source_format="srt")
    model.set_silence_intervals([{"start_ms": 3000, "end_ms": 4200}])
    plan = model.generate_plan("clean_tutorial")
    adapter = Adapter()

    result = apply_ai_script_plan_to_adapter(plan, adapter)

    assert result.applied["subtitle_rows"] == len(adapter.subtitles)
    assert result.applied["cut_intents"] == len(adapter.cuts)
    assert adapter.cuts and adapter.cuts[0]["requires_review"] is True
    assert adapter.sidecar["plan_id"] == plan.id


def test_script_edit_panel_widget_imports_and_generates_without_full_editor(monkeypatch):
    from PySide6.QtWidgets import QApplication

    import app.ai_providers as providers
    from app.ai_script_edit_panel import ScriptEditPanel

    fake_settings = FakeSettings()
    monkeypatch.setattr(providers, "_provider_settings", lambda: fake_settings)
    for key in (
        "TIGERCAPTURE_AI_PROVIDER",
        "TIGERCAPTURE_QWEN_MODEL_PATH",
        "TIGERCAPTURE_QWEN_RUNNER_COMMAND",
        "TIGERCAPTURE_QWEN_ENDPOINT",
        "TIGERCAPTURE_LOCAL_LLM_COMMAND",
        "TIGERCAPTURE_CODEX_MCP_ENABLED",
        "TIGERCAPTURE_CLAUDE_MCP_ENABLED",
    ):
        monkeypatch.delenv(key, raising=False)

    app = QApplication.instance() or QApplication([])
    panel = ScriptEditPanel()
    panel._transcript_input.setPlainText(SRT_SAMPLE)
    document = panel.import_transcript_from_text()
    panel._prompt_input.setPlainText("군더더기 빼고 자막 만들어줘")
    plan = panel.generate_from_prompt()

    assert app is not None
    assert len(document.segments) == 2
    assert plan.operations
    assert plan.metadata["prompt_resolved_action"] == "clean_tutorial"
    assert panel.selected_operation_ids()
    assert panel._segments_list.count() == 2
    assert panel._operations_list.count() == len(plan.operations)
    assert panel._provider_combo.findData("qwen_local") >= 0
    assert panel._provider_setup_btn.toolTip()
    assert "기본 무료 AI는 아직 설치되지 않았습니다" in panel._provider_detail_label.text()
    assert fake_settings.values == {}


def test_qa_tool_writes_ai_script_edit_report(tmp_path, monkeypatch):
    from tools import qa_ai_script_edit_integration

    out = tmp_path / "ai_script_edit_integration_qa.json"
    monkeypatch.setattr("sys.argv", ["qa_ai_script_edit_integration.py", "--out", str(out)])

    assert qa_ai_script_edit_integration.main() == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["ok"] is True
    assert report["checks"]["panel_generated_plan"] is True
    assert report["summary"]["subtitle_rows"] >= 1
    assert report["summary"]["review_cut_intents"] >= 1
