from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace


def _fake_style_bert_root(root: Path) -> Path:
    (root / "venv" / "Scripts").mkdir(parents=True)
    (root / "venv" / "Scripts" / "python.exe").write_text("", encoding="utf-8")
    (root / "server_fastapi.py").write_text("# fake server\n", encoding="utf-8")
    model = root / "model_assets" / "heroine"
    model.mkdir(parents=True)
    (model / "config.json").write_text("{}", encoding="utf-8")
    (model / "heroine.safetensors").write_text("", encoding="utf-8")
    return root


def _fake_style_bert_training_root(root: Path) -> Path:
    root = _fake_style_bert_root(root)
    tabs = root / "gradio_tabs"
    tabs.mkdir(parents=True)
    (tabs / "dataset.py").write_text("# fake dataset ui\n", encoding="utf-8")
    (tabs / "train.py").write_text("# fake train ui\n", encoding="utf-8")
    (root / "Dataset.bat").write_text("python -m gradio_tabs.dataset\n", encoding="utf-8")
    (root / "Train.bat").write_text("python -m gradio_tabs.train\n", encoding="utf-8")
    return root


def _fake_kokoro_root(root: Path) -> Path:
    package = root / "python"
    (package / "kokoro").mkdir(parents=True)
    (package / "soundfile.py").write_text("# fake soundfile\n", encoding="utf-8")
    (package / "kokoro-0.9.9.dist-info").mkdir()
    (package / "kokoro-0.9.9.dist-info" / "METADATA").write_text("Version: 0.9.9\n", encoding="utf-8")
    return root


def test_tts_provider_status_detects_valid_sidecar(tmp_path):
    from app.tts_setup import TTS_ENV_ENDPOINT, TTS_ENV_ROOT, tts_provider_status

    root = _fake_style_bert_root(tmp_path / "Style-Bert-VITS2")
    status = tts_provider_status(
        {
            TTS_ENV_ROOT: str(root),
            TTS_ENV_ENDPOINT: "http://127.0.0.1:5010",
        }
    )

    assert status["provider_id"] == "style_bert_vits2_sidecar"
    assert status["installed"] is True
    assert status["available"] is True
    assert status["setup_state"] == "ready_to_start"
    assert status["endpoint"] == "http://127.0.0.1:5010"
    assert status["root"]["model_names"] == ["heroine"]
    assert status["server_command"][1].endswith("server_fastapi.py")


def test_tts_install_plan_and_view_are_safe_contracts(tmp_path):
    from app.tts_setup import TTS_ENV_ROOT, tts_install_execution_gate, tts_install_plan, tts_setup_view_model

    missing_root = tmp_path / "missing"
    view = tts_setup_view_model({TTS_ENV_ROOT: str(missing_root)})
    plan = tts_install_plan(tmp_path / "tts_sidecar")
    gate = tts_install_execution_gate(tmp_path / "tts_sidecar")

    assert view["ready"] is False
    assert view["state"] == "needs_install"
    assert any(button["id"] == "install" for button in view["buttons"])
    assert plan["requires_user_consent"] is True
    assert plan["requires_network"] is True
    assert "AGPL" in plan["license_notice"]
    assert gate["requires_confirmation"] is True
    assert gate["plan"]["target_root"].endswith("tts_sidecar")


def test_tts_provider_status_reports_partial_install_missing_items(tmp_path):
    from app.tts_setup import TTS_ENV_ROOT, tts_provider_status

    partial_root = tmp_path / "Style-Bert-VITS2"
    partial_root.mkdir()
    (partial_root / "server_fastapi.py").write_text("# fake server\n", encoding="utf-8")

    status = tts_provider_status({TTS_ENV_ROOT: str(partial_root)})

    assert status["installed"] is False
    assert status["setup_state"] == "incomplete_install"
    assert "partial Style-Bert-VITS2 folder" in status["reason"]
    assert "venv/Scripts/python.exe" in status["root"]["missing"]
    assert "model_assets" in status["root"]["missing"]


def test_tts_provider_status_can_select_kokoro_external_runtime(tmp_path):
    from app.tts_kokoro import KOKORO_ENV_ROOT, KOKORO_PROVIDER_ID
    from app.tts_setup import TTS_ENV_PROVIDER, tts_install_plan, tts_provider_status, tts_setup_view_model

    root = _fake_kokoro_root(tmp_path / "kokoro")
    env = {
        TTS_ENV_PROVIDER: KOKORO_PROVIDER_ID,
        KOKORO_ENV_ROOT: str(root),
    }
    status = tts_provider_status(env)
    view = tts_setup_view_model(env)
    plan = tts_install_plan(tmp_path / "kokoro_target", provider_id=KOKORO_PROVIDER_ID)

    assert status["provider_id"] == KOKORO_PROVIDER_ID
    assert status["available"] is True
    assert status["requires_server"] is False
    assert status["root"]["model_names"][0] == "af_heart"
    assert view["provider_id"] == KOKORO_PROVIDER_ID
    assert view["requires_server"] is False
    assert any(row["provider_id"] == KOKORO_PROVIDER_ID for row in view["providers"])
    assert plan["target_root"].endswith("kokoro_target")
    assert plan["commands"]["install"][1].endswith("install_kokoro_tts.py")


def test_tts_actions_are_registered_and_readable(tmp_path):
    from app.actions.registry import ActionRegistry

    registry = ActionRegistry()
    ids = {row["id"] for row in registry.list_actions()}

    assert "tts.provider.status" in ids
    assert "tts.provider.select" in ids
    assert "tts.install.plan" in ids
    assert "tts.connect_installed_sidecar" in ids
    assert "tts.server.ensure_running" in ids
    assert "tts.voice.list" in ids
    assert "tts.model.training.plan" in ids
    assert "tts.model.training.execution_gate" in ids
    assert "tts.model.training.prepare_workspace" in ids
    assert "tts.model.training.launch_dataset" in ids
    assert "tts.model.training.launch_train" in ids
    assert "tts.model.training.register_result" in ids
    assert "tts.subtitle.plan" in ids
    assert "tts.subtitle.generate_to_timeline" in ids
    assert "tts.subtitle.apply_actor_lipsync" in ids
    assert "tts.dialogue.plan_actor_take" in ids
    assert "tts.dialogue.generate_actor_take" in ids

    result = registry.execute("tts.install.plan", {"install_root": str(tmp_path / "tts")})
    assert result.ok is True
    assert result.result["provider_id"] == "style_bert_vits2_sidecar"


def test_tts_model_training_plan_and_gate_use_external_sidecar_tools(tmp_path):
    from app.tts_model_training import tts_model_training_execution_gate, tts_model_training_plan
    from app.tts_setup import TTS_ENV_ROOT

    root = _fake_style_bert_training_root(tmp_path / "Style-Bert-VITS2")
    plan = tts_model_training_plan(model_name="Zoe Alt!", env={TTS_ENV_ROOT: str(root)})
    gate = tts_model_training_execution_gate(model_name="Zoe Alt!", env={TTS_ENV_ROOT: str(root)})

    assert plan["ready"] is True
    assert plan["model_name"] == "Zoe_Alt"
    assert plan["raw_audio_dir"].endswith("Data\\Zoe_Alt\\raw") or plan["raw_audio_dir"].endswith("Data/Zoe_Alt/raw")
    assert plan["expected_model_asset_dir"].endswith("model_assets\\Zoe_Alt") or plan[
        "expected_model_asset_dir"
    ].endswith("model_assets/Zoe_Alt")
    assert plan["commands"]["dataset_ui"][1:] == ["-m", "gradio_tabs.dataset"]
    assert plan["commands"]["train_ui"][1:] == ["-m", "gradio_tabs.train"]
    assert gate["requires_confirmation"] is True
    assert gate["gpu_heavy"] is True


def test_tts_model_training_prepare_workspace_copies_source_audio(tmp_path):
    from app.tts_model_training import tts_model_training_prepare_workspace
    from app.tts_setup import TTS_ENV_ROOT

    root = _fake_style_bert_training_root(tmp_path / "Style-Bert-VITS2")
    source = tmp_path / "voice_source"
    source.mkdir()
    (source / "line01.wav").write_bytes(b"RIFFfake")
    (source / "line02.mp3").write_bytes(b"ID3fake")
    (source / "notes.txt").write_text("skip", encoding="utf-8")

    result = tts_model_training_prepare_workspace(
        model_name="custom_voice",
        source_audio_dir=source,
        env={TTS_ENV_ROOT: str(root)},
    )

    raw = Path(result["raw_audio_dir"])
    assert result["prepared"] is True
    assert result["copied_count"] == 2
    assert (raw / "line01.wav").is_file()
    assert (raw / "line02.mp3").is_file()
    assert not (raw / "notes.txt").exists()


def test_tts_model_training_register_result_detects_completed_model(tmp_path):
    from app.tts_model_training import tts_model_training_register_result
    from app.tts_setup import TTS_ENV_ROOT

    root = _fake_style_bert_training_root(tmp_path / "Style-Bert-VITS2")
    model = root / "model_assets" / "custom_voice"
    model.mkdir(parents=True)
    (model / "config.json").write_text("{}", encoding="utf-8")
    (model / "custom_voice.safetensors").write_text("", encoding="utf-8")

    result = tts_model_training_register_result(
        model_name="custom_voice",
        env={TTS_ENV_ROOT: str(root)},
    )

    assert result["available"] is True
    assert result["registered"] is True
    assert "custom_voice" in result["models"]


class _SubtitlePanel:
    def __init__(self):
        self._rows = [
            SimpleNamespace(start_ms=1000, end_ms=2200, text="Hello ZOE", style={}),
            SimpleNamespace(start_ms=3500, end_ms=4800, text="Second line", style={}),
        ]

    def subtitles(self):
        return list(self._rows)


class _TtsOwner:
    def __init__(self):
        self._subtitle_panel = _SubtitlePanel()
        self._audio_tracks = []
        self._action_imported_media = []
        self.changes = []

    def _register_change(self, label):
        self.changes.append(label)


def _ready_zoe_status():
    return {
        "provider_id": "style_bert_vits2_sidecar",
        "available": True,
        "endpoint": "http://127.0.0.1:5999",
        "root": {"model_names": ["amitaro", "koharune-ami", "zoe"]},
    }


def _ready_japanese_and_zoe_status():
    return {
        "provider_id": "style_bert_vits2_sidecar",
        "available": True,
        "endpoint": "http://127.0.0.1:5999",
        "root": {"model_names": ["amitaro", "jvnv-F1-jp", "jvnv-F2-jp", "koharune-ami", "zoe"]},
    }


def _ready_kokoro_status():
    return {
        "provider_id": "kokoro_local",
        "available": True,
        "requires_server": False,
        "endpoint": "",
        "root": {"model_names": ["af_heart", "jf_alpha"]},
    }


def _fake_live2d_model_with_motions(root: Path) -> Path:
    model_dir = root / "live2d_model"
    motion_dir = model_dir / "motions"
    motion_dir.mkdir(parents=True)
    for name in ("idle_01", "greet_wave", "explain_body", "happy_emphasis"):
        (motion_dir / f"{name}.motion3.json").write_text("{}", encoding="utf-8")
    model_path = model_dir / "avatar.model3.json"
    model_path.write_text(
        json.dumps(
            {
                "Version": 3,
                "FileReferences": {
                    "Motions": {
                        "Idle": [{"File": "motions/idle_01.motion3.json"}],
                        "Greeting": [{"File": "motions/greet_wave.motion3.json"}],
                        "Talk": [{"File": "motions/explain_body.motion3.json"}],
                        "Happy": [{"File": "motions/happy_emphasis.motion3.json"}],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    return model_path


def test_tts_subtitle_plan_prefers_default_koharune(monkeypatch, tmp_path):
    from app.actions import build_default_action_registry
    import app.tts_setup as tts_setup

    monkeypatch.setattr(tts_setup, "tts_provider_status", lambda: _ready_zoe_status())
    owner = _TtsOwner()
    registry = build_default_action_registry(owner)

    result = registry.execute("tts.subtitle.plan", {"output_dir": str(tmp_path / "tts")}).to_dict()

    assert result["ok"] is True
    assert result["result"]["model_name"] == "koharune-ami"
    assert result["result"]["subtitle_count"] == 2
    assert result["result"]["rows"][0]["start_ms"] == 1000
    assert "tts_sub_0000_" in result["result"]["rows"][0]["output_path"]


def test_tts_subtitle_plan_separates_japanese_voice_from_korean_caption(monkeypatch, tmp_path):
    from app.actions import build_default_action_registry
    import app.tts_setup as tts_setup

    monkeypatch.setattr(tts_setup, "tts_provider_status", lambda: _ready_japanese_and_zoe_status())
    owner = _TtsOwner()
    owner._subtitle_panel._rows = [
        SimpleNamespace(
            start_ms=1200,
            end_ms=3100,
            text="\uc624\ub298\uc740 \ub3c4\ucfc4\uc758 \ubc24\uac70\ub9ac\ub97c \ub530\ub77c\uac11\ub2c8\ub2e4.",
            style={"tts_text": "\u4eca\u65e5\u306f\u6771\u4eac\u306e\u591c\u666f\u306b\u5408\u308f\u305b\u3066\u7de8\u96c6\u3057\u307e\u3059\u3002"},
        )
    ]
    registry = build_default_action_registry(owner)

    result = registry.execute("tts.subtitle.plan", {"output_dir": str(tmp_path / "tts")}).to_dict()

    assert result["ok"] is True
    row = result["result"]["rows"][0]
    assert row["text"] == "\u4eca\u65e5\u306f\u6771\u4eac\u306e\u591c\u666f\u306b\u5408\u308f\u305b\u3066\u7de8\u96c6\u3057\u307e\u3059\u3002"
    assert row["tts_text"] == "\u4eca\u65e5\u306f\u6771\u4eac\u306e\u591c\u666f\u306b\u5408\u308f\u305b\u3066\u7de8\u96c6\u3057\u307e\u3059\u3002"
    assert row["subtitle_text"] == "\uc624\ub298\uc740 \ub3c4\ucfc4\uc758 \ubc24\uac70\ub9ac\ub97c \ub530\ub77c\uac11\ub2c8\ub2e4."
    assert row["display_text"] == "\uc624\ub298\uc740 \ub3c4\ucfc4\uc758 \ubc24\uac70\ub9ac\ub97c \ub530\ub77c\uac11\ub2c8\ub2e4."


def test_tts_subtitle_plan_can_use_kokoro_provider(monkeypatch, tmp_path):
    from app.actions import build_default_action_registry
    import app.tts_setup as tts_setup

    monkeypatch.setattr(tts_setup, "tts_provider_status", lambda **_kwargs: _ready_kokoro_status())
    owner = _TtsOwner()
    registry = build_default_action_registry(owner)

    result = registry.execute(
        "tts.subtitle.plan",
        {"provider_id": "kokoro_local", "model_name": "jf_alpha", "output_dir": str(tmp_path / "tts")},
    ).to_dict()

    assert result["ok"] is True
    assert result["result"]["provider_id"] == "kokoro_local"
    assert result["result"]["requires_server"] is False
    assert result["result"]["model_name"] == "jf_alpha"


def test_tts_subtitle_generation_places_audio_clips(monkeypatch, tmp_path):
    from app.actions import build_default_action_registry
    import app.tts_setup as tts_setup
    import app.tts_subtitle_workflow as workflow

    monkeypatch.setattr(tts_setup, "tts_provider_status", lambda: _ready_zoe_status())

    def _fake_synthesize(rows, **kwargs):
        generated = []
        for idx, row in enumerate(rows):
            path = tmp_path / f"voice_{idx}.wav"
            path.write_bytes(b"RIFF$\x00\x00\x00WAVEfmt ")
            generated.append(
                {
                    **dict(row),
                    "path": str(path),
                    "byte_count": path.stat().st_size,
                    "generated_duration_ms": 900 + idx,
                    "model_name": kwargs.get("model_name", ""),
                    "endpoint": kwargs.get("endpoint", ""),
                }
            )
        return generated

    monkeypatch.setattr(workflow, "synthesize_subtitle_rows", _fake_synthesize)
    owner = _TtsOwner()
    registry = build_default_action_registry(owner)

    result = registry.execute(
        "tts.subtitle.generate_to_timeline",
        {
            "output_dir": str(tmp_path / "tts"),
            "track_name": "ZOE Dialogue",
            "auto_start_server": False,
        },
    ).to_dict()

    assert result["ok"] is True
    assert result["result"]["model_name"] == "koharune-ami"
    assert result["result"]["clip_count"] == 2
    assert len(owner._audio_tracks) == 1
    track = owner._audio_tracks[0]
    assert track.label == "ZOE Dialogue"
    assert track.track_type == "dialogue"
    assert [clip.offset_ms for clip in track.clips] == [1000, 3500]
    assert [clip.trim_end_ms for clip in track.clips] == [900, 901]
    assert len(owner._action_imported_media) == 2
    assert owner.changes[-1] == "Generate TTS subtitle track"


def test_tts_subtitle_generation_skips_server_for_kokoro(monkeypatch, tmp_path):
    from app.actions import build_default_action_registry
    import app.tts_kokoro as kokoro
    import app.tts_setup as tts_setup

    monkeypatch.setattr(tts_setup, "tts_provider_status", lambda **_kwargs: _ready_kokoro_status())

    def _fake_kokoro(**kwargs):
        from app.tts_synthesis import VoiceSynthesisResult

        path = Path(kwargs["output_path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"RIFF$\x00\x00\x00WAVEfmt ")
        return VoiceSynthesisResult(path=path, byte_count=path.stat().st_size, duration_ms=777, endpoint="", model_name=kwargs["voice"])

    monkeypatch.setattr(kokoro, "synthesize_kokoro_voice", _fake_kokoro)
    owner = _TtsOwner()
    registry = build_default_action_registry(owner)

    result = registry.execute(
        "tts.subtitle.generate_to_timeline",
        {
            "provider_id": "kokoro_local",
            "model_name": "af_heart",
            "output_dir": str(tmp_path / "tts"),
            "auto_start_server": True,
        },
    ).to_dict()

    assert result["ok"] is True
    assert result["result"]["provider_id"] == "kokoro_local"
    assert result["result"]["server"]["ready"] is True
    assert result["result"]["server"]["started"] is False
    assert result["result"]["clip_count"] == 2


def test_tts_apply_actor_lipsync_bakes_live2d_mouth_keyframes():
    from app.actions import build_default_action_registry
    from app.live2d.actor_track import Live2DActorClip, Live2DActorTrack

    owner = _TtsOwner()
    clip = Live2DActorClip(model_path="avatar.model3.json", start_ms=1000, duration_ms=3000)
    owner._live2d_actor_tracks = [Live2DActorTrack(id=7, clips=[clip])]
    registry = build_default_action_registry(owner)

    result = registry.execute(
        "tts.subtitle.apply_actor_lipsync",
        {
            "actor_track_id": 7,
            "rows": [
                {"timeline_in_ms": 1200, "duration_ms": 800, "text": "Hello ZOE"},
                {"timeline_in_ms": 2400, "duration_ms": 600, "text": "Second line"},
            ],
        },
    ).to_dict()

    assert result["ok"] is True
    assert result["result"]["applied"] is True
    assert set(result["result"]["parameter_tracks"]) == {
        "ParamMouthOpenY",
        "ParamMouthForm",
        "ParamEyeLOpen",
        "ParamEyeROpen",
    }
    assert result["result"]["blink_count"] >= 1
    assert clip.parameter_keyframes["ParamMouthOpenY"][0]["time_ms"] == 166
    assert any(row["value"] > 0.25 for row in clip.parameter_keyframes["ParamMouthOpenY"])
    assert any(row["value"] == 0.0 for row in clip.parameter_keyframes["ParamEyeLOpen"])
    assert any(row["value"] == 1.0 for row in clip.parameter_keyframes["ParamEyeROpen"])
    assert clip.tts_lipsync_payload["schema"] == "tigercapture.tts_actor_lipsync.v1"
    assert owner.changes[-1] == "Apply TTS actor lip-sync"


def test_tts_generation_can_apply_actor_lipsync(monkeypatch, tmp_path):
    from app.actions import build_default_action_registry
    from app.live2d.actor_track import Live2DActorClip, Live2DActorTrack
    import app.tts_setup as tts_setup
    import app.tts_subtitle_workflow as workflow

    monkeypatch.setattr(tts_setup, "tts_provider_status", lambda: _ready_zoe_status())

    def _fake_synthesize(rows, **kwargs):
        generated = []
        for idx, row in enumerate(rows):
            path = tmp_path / f"voice_lip_{idx}.wav"
            path.write_bytes(b"RIFF$\x00\x00\x00WAVEfmt ")
            generated.append(
                {
                    **dict(row),
                    "path": str(path),
                    "byte_count": path.stat().st_size,
                    "generated_duration_ms": 700,
                    "model_name": kwargs.get("model_name", ""),
                    "endpoint": kwargs.get("endpoint", ""),
                }
            )
        return generated

    monkeypatch.setattr(workflow, "synthesize_subtitle_rows", _fake_synthesize)
    owner = _TtsOwner()
    clip = Live2DActorClip(model_path="avatar.model3.json", start_ms=0, duration_ms=6000)
    owner._live2d_actor_tracks = [Live2DActorTrack(id=9, clips=[clip])]
    registry = build_default_action_registry(owner)

    result = registry.execute(
        "tts.subtitle.generate_to_timeline",
        {
            "output_dir": str(tmp_path / "tts"),
            "track_name": "ZOE Dialogue",
            "auto_start_server": False,
            "apply_actor_lipsync": True,
            "actor_track_id": 9,
        },
    ).to_dict()

    assert result["ok"] is True
    assert result["result"]["clip_count"] == 2
    assert result["result"]["actor_lipsync"]["applied"] is True
    assert "ParamMouthOpenY" in clip.parameter_keyframes
    assert "ParamEyeLOpen" in clip.parameter_keyframes
    assert owner.changes[-1] == "Generate TTS subtitle track"


def test_live2d_dialogue_placement_fits_visible_alpha_bounds():
    from PIL import Image, ImageDraw
    from app.live2d.dialogue_placement import alpha_bounds, fit_transform_from_bounds

    img = Image.new("RGBA", (400, 300), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rectangle((230, 80, 330, 285), fill=(255, 255, 255, 255))

    bounds = alpha_bounds(img)
    result = fit_transform_from_bounds(
        bounds,
        current_pos_x=0.5,
        current_pos_y=0.5,
        current_scale=1.0,
        preset="bottom_right",
        size_preset="auto_fit",
        canvas_width=400,
        canvas_height=300,
    )

    assert bounds["ok"] is True
    assert result["measured"] is True
    assert result["transform"]["pos_x"] > 0.63
    assert result["transform"]["scale"] > 0.5
    assert result["target"]["bottom_px"] > 295


def test_live2d_dialogue_motion_adds_body_head_and_breath_keys():
    from app.live2d.actor_track import Live2DActorClip
    from app.live2d.dialogue_motion import apply_natural_dialogue_motion_to_clip

    clip = Live2DActorClip(model_path="avatar.model3.json", start_ms=1000, duration_ms=5000)
    result = apply_natural_dialogue_motion_to_clip(
        clip,
        rows=[{"timeline_in_ms": 1200, "duration_ms": 1600, "text": "こんにちは"}],
        interval_ms=500,
    )

    assert result["schema"] == "tigerstudio.live2d.dialogue_motion.v1"
    assert "ParamAngleX" in clip.parameter_keyframes
    assert "ParamBodyAngleX" in clip.parameter_keyframes
    assert "ParamBreath" in clip.parameter_keyframes
    assert "ParamArmLA" in clip.parameter_keyframes
    assert "ParamFaceForm" in clip.parameter_keyframes
    assert "ParamHandAngleR" in clip.parameter_keyframes
    assert len(clip.parameter_keyframes["ParamAngleX"]) >= 5
    assert any(abs(row["value"]) > 6.5 for row in clip.parameter_keyframes["ParamAngleX"])
    assert any(row["value"] > 1.0 for row in clip.parameter_keyframes["ParamArmLA"])
    assert result["gesture_beats"]
    assert result["gesture_beats"][0]["gesture_id"] == "greet"


def test_live2d_dialogue_motion_storyboards_authored_model_motions(tmp_path):
    from app.live2d.actor_track import Live2DActorClip, Live2DActorTrack
    from app.live2d.dialogue_motion import (
        apply_authored_dialogue_motion_storyboard_to_track,
        apply_natural_dialogue_motion_to_clip,
        build_authored_dialogue_motion_storyboard,
    )

    model_path = _fake_live2d_model_with_motions(tmp_path)
    rows = [
        {"timeline_in_ms": 1000, "duration_ms": 1200, "text": "hello"},
        {"timeline_in_ms": 2500, "duration_ms": 1200, "text": "explain this"},
        {"timeline_in_ms": 4000, "duration_ms": 1000, "text": "finish!"},
    ]
    clip = Live2DActorClip(model_path=str(model_path), start_ms=1000, duration_ms=5000)
    track = Live2DActorTrack(id=18, clips=[clip])

    plan = build_authored_dialogue_motion_storyboard(
        str(model_path),
        rows,
        actor_start_ms=clip.start_ms,
        actor_duration_ms=clip.duration_ms,
    )
    apply_natural_dialogue_motion_to_clip(clip, rows=rows, interval_ms=500)
    result = apply_authored_dialogue_motion_storyboard_to_track(track, clip, rows=rows)

    assert plan["available"] is True
    assert plan["motion_count"] == 4
    assert plan["line_motion_count"] == 3
    assert result["applied"] is True
    assert result["created"] == 3
    assert len(track.clips) == 3
    assert {segment.motion_group for segment in track.clips} >= {"Greeting", "Talk"}
    assert all(segment.motion_storyboard_payload["kind"] == "live2d_dialogue_motion_storyboard" for segment in track.clips)
    assert any("ParamAngleX" in segment.parameter_keyframes for segment in track.clips)


def test_stable_synthesis_params_infer_japanese_defaults():
    from app.tts_subtitle_workflow import preferred_dialogue_model_name, stable_synthesis_params

    rows = [{"text": "こんにちは。今日は短い動画を作ります。"}]
    params = stable_synthesis_params(rows, model_name="zoe")

    assert params["language"] == "JP"
    assert params["sdp_ratio"] == 0.2
    assert params["noise"] == 0.45
    assert params["noisew"] == 0.6
    assert params["length"] == 1.08
    assert preferred_dialogue_model_name(_ready_japanese_and_zoe_status(), rows) == "koharune-ami"
    assert preferred_dialogue_model_name(_ready_japanese_and_zoe_status(), rows, requested="zoe") == "zoe"
    assert preferred_dialogue_model_name(_ready_japanese_and_zoe_status(), rows, requested="jvnv-F1-jp") == "jvnv-F1-jp"


def test_tts_dialogue_plan_actor_take_lists_voice_actor_and_placement(monkeypatch):
    from app.actions import build_default_action_registry
    from app.live2d.actor_track import Live2DActorClip, Live2DActorTrack
    import app.tts_setup as tts_setup

    monkeypatch.setattr(tts_setup, "tts_provider_status", lambda: _ready_zoe_status())
    owner = _TtsOwner()
    clip = Live2DActorClip(model_path="avatar.model3.json", start_ms=0, duration_ms=9000)
    owner._live2d_actor_tracks = [Live2DActorTrack(id=14, label="Host", clips=[clip])]
    registry = build_default_action_registry(owner)

    result = registry.execute(
        "tts.dialogue.plan_actor_take",
        {"dialogue_text": "Hello.\nSecond line."},
    ).to_dict()

    assert result["ok"] is True
    payload = result["result"]
    assert payload["dialogue"]["line_count"] == 2
    assert payload["recommended"]["actor_target_id"] == "live2d:14:0"
    assert payload["recommended"]["model_name"] == "koharune-ami"
    assert any(row["id"] == "bottom_right" for row in payload["placement_presets"])
    assert any(row["id"] == "auto_fit" for row in payload["size_presets"])
    assert payload["live2d_targets"][0]["label"].startswith("Live2D")


def test_tts_dialogue_plan_actor_take_uses_koharune_default_for_japanese_text(monkeypatch):
    from app.actions import build_default_action_registry
    from app.live2d.actor_track import Live2DActorClip, Live2DActorTrack
    import app.tts_setup as tts_setup

    monkeypatch.setattr(tts_setup, "tts_provider_status", lambda: _ready_japanese_and_zoe_status())
    owner = _TtsOwner()
    clip = Live2DActorClip(model_path="avatar.model3.json", start_ms=0, duration_ms=9000)
    owner._live2d_actor_tracks = [Live2DActorTrack(id=15, label="Host", clips=[clip])]
    registry = build_default_action_registry(owner)

    result = registry.execute(
        "tts.dialogue.plan_actor_take",
        {"dialogue_text": "こんにちは。今日は短い動画を作ります。"},
    ).to_dict()

    assert result["ok"] is True
    assert result["result"]["recommended"]["model_name"] == "koharune-ami"


def test_tts_dialogue_plan_actor_take_accepts_spoken_display_pairs(monkeypatch):
    from app.actions import build_default_action_registry
    from app.live2d.actor_track import Live2DActorClip, Live2DActorTrack
    import app.tts_setup as tts_setup

    monkeypatch.setattr(tts_setup, "tts_provider_status", lambda: _ready_japanese_and_zoe_status())
    owner = _TtsOwner()
    clip = Live2DActorClip(model_path="avatar.model3.json", start_ms=0, duration_ms=9000)
    owner._live2d_actor_tracks = [Live2DActorTrack(id=16, label="Host", clips=[clip])]
    registry = build_default_action_registry(owner)

    result = registry.execute(
        "tts.dialogue.plan_actor_take",
        {
            "dialogue_text": "\u3053\u3093\u306b\u3061\u306f\u3002 => \uc548\ub155\ud558\uc138\uc694.\n"
            "\u6620\u50cf\u306b\u5408\u308f\u305b\u3066\u58f0\u3092\u91cd\u306d\u307e\u3059\u3002 => \uc601\uc0c1\uc5d0 \ub9de\ucdb0 \ubaa9\uc18c\ub9ac\ub97c \uc5b9\uc5b4\uc694.",
        },
    ).to_dict()

    assert result["ok"] is True
    rows = result["result"]["dialogue"]["rows"]
    assert rows[0]["text"] == "\u3053\u3093\u306b\u3061\u306f\u3002"
    assert rows[0]["tts_text"] == "\u3053\u3093\u306b\u3061\u306f\u3002"
    assert rows[0]["subtitle_text"] == "\uc548\ub155\ud558\uc138\uc694."
    assert rows[1]["display_text"] == "\uc601\uc0c1\uc5d0 \ub9de\ucdb0 \ubaa9\uc18c\ub9ac\ub97c \uc5b9\uc5b4\uc694."
    assert result["result"]["recommended"]["model_name"] == "koharune-ami"


def test_tts_dialogue_generate_actor_take_creates_subtitles_audio_and_blink(monkeypatch, tmp_path):
    from app.actions import build_default_action_registry
    from app.live2d.actor_track import Live2DActorClip, Live2DActorTrack
    import app.tts_setup as tts_setup
    import app.tts_subtitle_workflow as workflow

    monkeypatch.setattr(tts_setup, "tts_provider_status", lambda: _ready_zoe_status())

    def _fake_synthesize(rows, **kwargs):
        generated = []
        for idx, row in enumerate(rows):
            path = tmp_path / f"dialogue_take_{idx}.wav"
            path.write_bytes(b"RIFF$\x00\x00\x00WAVEfmt ")
            generated.append(
                {
                    **dict(row),
                    "path": str(path),
                    "byte_count": path.stat().st_size,
                    "generated_duration_ms": int(row.get("duration_ms", 900) or 900),
                    "model_name": kwargs.get("model_name", ""),
                    "endpoint": kwargs.get("endpoint", ""),
                }
            )
        return generated

    monkeypatch.setattr(workflow, "synthesize_subtitle_rows", _fake_synthesize)
    owner = _TtsOwner()
    clip = Live2DActorClip(model_path="avatar.model3.json", start_ms=0, duration_ms=9000)
    owner._live2d_actor_tracks = [Live2DActorTrack(id=14, clips=[clip])]
    registry = build_default_action_registry(owner)

    result = registry.execute(
        "tts.dialogue.generate_actor_take",
        {
            "dialogue_text": "안녕, 오늘은 자동 대사 테스트야.\n눈도 자연스럽게 깜박여야 해.",
            "output_dir": str(tmp_path / "tts"),
            "track_name": "AI Dialogue Take",
            "auto_start_server": False,
        },
    ).to_dict()

    assert result["ok"] is True
    payload = result["result"]
    assert payload["dialogue_line_count"] == 2
    assert payload["subtitles"]["created"] is True
    assert payload["subtitles"]["count"] == 2
    assert len(owner._subtitle_panel.subtitles()) == 4
    assert payload["tts"]["clip_count"] == 2
    assert payload["actor_lipsync"]["applied"] is True
    assert payload["actor_target"]["track_id"] == 14
    assert payload["placement"]["applied"] is True
    assert payload["actor_motion"]["applied"] is True
    assert payload["placement"]["transform"]["pos_x"] > 0.5
    assert "ParamMouthOpenY" in clip.parameter_keyframes
    assert "ParamEyeLOpen" in clip.parameter_keyframes
    assert "ParamAngleX" in clip.parameter_keyframes
    assert "ParamBodyAngleX" in clip.parameter_keyframes
    assert "ParamBreath" in clip.parameter_keyframes
    assert "ParamArmLA" in clip.parameter_keyframes
    assert "ParamFaceForm" in clip.parameter_keyframes
    assert "ParamHandAngleR" in clip.parameter_keyframes
    assert clip.kf_pos_x
    assert clip.dialogue_placement_payload["schema"] == "tigerstudio.live2d.dialogue_placement.v1"
    assert clip.dialogue_motion_payload["schema"] == "tigerstudio.live2d.dialogue_motion.v1"
    assert any(row["value"] == 0.0 for row in clip.parameter_keyframes["ParamEyeLOpen"])
    assert clip.tts_lipsync_payload["blink_count"] >= 1
    assert owner.changes[-1] == "Generate TTS subtitle track"


def test_tts_dialogue_generate_actor_take_speaks_japanese_and_shows_korean(monkeypatch, tmp_path):
    from app.actions import build_default_action_registry
    from app.live2d.actor_track import Live2DActorClip, Live2DActorTrack
    import app.tts_setup as tts_setup
    import app.tts_subtitle_workflow as workflow

    monkeypatch.setattr(tts_setup, "tts_provider_status", lambda: _ready_japanese_and_zoe_status())
    synthesized_rows = []

    def _fake_synthesize(rows, **kwargs):
        synthesized_rows.extend(dict(row) for row in rows)
        generated = []
        for idx, row in enumerate(rows):
            path = tmp_path / f"bilingual_take_{idx}.wav"
            path.write_bytes(b"RIFF$\x00\x00\x00WAVEfmt ")
            generated.append(
                {
                    **dict(row),
                    "path": str(path),
                    "byte_count": path.stat().st_size,
                    "generated_duration_ms": int(row.get("duration_ms", 900) or 900),
                    "model_name": kwargs.get("model_name", ""),
                    "endpoint": kwargs.get("endpoint", ""),
                }
            )
        return generated

    monkeypatch.setattr(workflow, "synthesize_subtitle_rows", _fake_synthesize)
    owner = _TtsOwner()
    clip = Live2DActorClip(model_path="avatar.model3.json", start_ms=0, duration_ms=9000)
    owner._live2d_actor_tracks = [Live2DActorTrack(id=17, clips=[clip])]
    registry = build_default_action_registry(owner)

    result = registry.execute(
        "tts.dialogue.generate_actor_take",
        {
            "dialogue_text": "\u3053\u3093\u306b\u3061\u306f\u3002 => \uc548\ub155\ud558\uc138\uc694.",
            "output_dir": str(tmp_path / "tts"),
            "auto_start_server": False,
        },
    ).to_dict()

    assert result["ok"] is True
    assert synthesized_rows[0]["text"] == "\u3053\u3093\u306b\u3061\u306f\u3002"
    assert synthesized_rows[0]["tts_text"] == "\u3053\u3093\u306b\u3061\u306f\u3002"
    assert synthesized_rows[0]["subtitle_text"] == "\uc548\ub155\ud558\uc138\uc694."
    created_subtitle = owner._subtitle_panel.subtitles()[-1]
    assert created_subtitle.text == "\uc548\ub155\ud558\uc138\uc694."
    assert created_subtitle.style["tts_text"] == "\u3053\u3093\u306b\u3061\u306f\u3002"
    clip_row = result["result"]["tts"]["clips"][0]
    assert clip_row["text"] == "\u3053\u3093\u306b\u3061\u306f\u3002"
    assert clip_row["subtitle_text"] == "\uc548\ub155\ud558\uc138\uc694."


def test_tts_dialogue_generate_actor_take_applies_authored_live2d_motions(monkeypatch, tmp_path):
    from app.actions import build_default_action_registry
    from app.live2d.actor_track import Live2DActorClip, Live2DActorTrack
    import app.tts_setup as tts_setup
    import app.tts_subtitle_workflow as workflow

    model_path = _fake_live2d_model_with_motions(tmp_path)
    monkeypatch.setattr(tts_setup, "tts_provider_status", lambda: _ready_japanese_and_zoe_status())

    def _fake_synthesize(rows, **kwargs):
        generated = []
        for idx, row in enumerate(rows):
            path = tmp_path / f"authored_motion_take_{idx}.wav"
            path.write_bytes(b"RIFF$\x00\x00\x00WAVEfmt ")
            generated.append(
                {
                    **dict(row),
                    "path": str(path),
                    "byte_count": path.stat().st_size,
                    "generated_duration_ms": int(row.get("duration_ms", 900) or 900),
                    "model_name": kwargs.get("model_name", ""),
                    "endpoint": kwargs.get("endpoint", ""),
                }
            )
        return generated

    monkeypatch.setattr(workflow, "synthesize_subtitle_rows", _fake_synthesize)
    owner = _TtsOwner()
    clip = Live2DActorClip(model_path=str(model_path), start_ms=0, duration_ms=7000)
    owner._live2d_actor_tracks = [Live2DActorTrack(id=19, clips=[clip])]
    registry = build_default_action_registry(owner)

    result = registry.execute(
        "tts.dialogue.generate_actor_take",
        {
            "dialogue_text": "こんにちは。 => 안녕하세요.\n"
            "映像に合わせて説明します。 => 영상에 맞춰 설명합니다.\n"
            "最後は明るく締めます！ => 마지막은 밝게 마무리합니다!",
            "output_dir": str(tmp_path / "tts"),
            "auto_start_server": False,
        },
    ).to_dict()

    assert result["ok"] is True
    payload = result["result"]
    authored = payload["actor_motion"]["authored_storyboard"]
    assert authored["applied"] is True
    assert authored["created"] == 3
    storyboard_clips = owner._live2d_actor_tracks[0].clips
    assert len(storyboard_clips) == 3
    assert {segment.motion_group for segment in storyboard_clips} >= {"Greeting", "Talk"}
    assert any("ParamMouthOpenY" in segment.parameter_keyframes for segment in storyboard_clips)
    assert all(segment.dialogue_motion_payload["authored_motion_storyboard_segment"]["schema"] for segment in storyboard_clips)


def test_tts_dialogue_generate_actor_take_can_create_actor_from_media_pool(monkeypatch, tmp_path):
    from app.actions import build_default_action_registry
    import app.tts_setup as tts_setup
    import app.tts_subtitle_workflow as workflow

    model_path = tmp_path / "character.model3.json"
    model_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(tts_setup, "tts_provider_status", lambda: _ready_zoe_status())

    def _fake_synthesize(rows, **kwargs):
        generated = []
        for idx, row in enumerate(rows):
            path = tmp_path / f"media_pool_take_{idx}.wav"
            path.write_bytes(b"RIFF$\x00\x00\x00WAVEfmt ")
            generated.append(
                {
                    **dict(row),
                    "path": str(path),
                    "byte_count": path.stat().st_size,
                    "generated_duration_ms": 900,
                    "model_name": kwargs.get("model_name", ""),
                    "endpoint": kwargs.get("endpoint", ""),
                }
            )
        return generated

    class _MediaPool:
        def media_pool_metadata(self):
            return [{"path": str(model_path), "kind": "?"}]

    monkeypatch.setattr(workflow, "synthesize_subtitle_rows", _fake_synthesize)
    owner = _TtsOwner()
    owner._media_pool = _MediaPool()
    registry = build_default_action_registry(owner)

    result = registry.execute(
        "tts.dialogue.generate_actor_take",
        {
            "dialogue_text": "Create actor from media pool.",
            "actor_target_id": "media_live2d:0",
            "output_dir": str(tmp_path / "tts"),
            "auto_start_server": False,
        },
    ).to_dict()

    assert result["ok"] is True
    payload = result["result"]
    assert payload["actor_target"]["source"] == "media_pool_created_actor"
    assert payload["actor_lipsync"]["applied"] is True
    assert len(owner._live2d_actor_tracks) == 1
    clip = owner._live2d_actor_tracks[0].clips[0]
    assert clip.model_path.endswith("character.model3.json")
    assert clip.dialogue_placement_payload["schema"] == "tigerstudio.live2d.dialogue_placement.v1"
    assert clip.dialogue_motion_payload["schema"] == "tigerstudio.live2d.dialogue_motion.v1"


def test_live2d_tts_lipsync_metadata_roundtrip():
    from app.live2d.actor_track import Live2DActorClip, Live2DActorTrack
    from app.project_io import _actor_track_to_dict, _live2d_actor_track_from_dict

    clip = Live2DActorClip(model_path="avatar.model3.json", start_ms=0, duration_ms=3000)
    clip.parameter_keyframes = {"ParamMouthOpenY": [{"time_ms": 100, "value": 0.6, "curve": "smoothstep"}]}
    clip.tts_lipsync_payload = {
        "schema": "tigercapture.tts_actor_lipsync.v1",
        "blink_count": 1,
        "parameter_keyframes": dict(clip.parameter_keyframes),
    }
    clip.tts_lipsync_source = "provided_rows"
    clip.dialogue_placement_payload = {"schema": "tigerstudio.live2d.dialogue_placement.v1", "measured": True}
    clip.dialogue_motion_payload = {"schema": "tigerstudio.live2d.dialogue_motion.v1", "style": "natural_dialogue"}
    restored = _live2d_actor_track_from_dict(_actor_track_to_dict(Live2DActorTrack(id=22, clips=[clip])))

    restored_clip = restored.clips[0]
    assert restored_clip.parameter_keyframes["ParamMouthOpenY"][0]["value"] == 0.6
    assert restored_clip.tts_lipsync_payload["schema"] == "tigercapture.tts_actor_lipsync.v1"
    assert restored_clip.tts_lipsync_payload["blink_count"] == 1
    assert restored_clip.tts_lipsync_source == "provided_rows"
    assert restored_clip.dialogue_placement_payload["schema"] == "tigerstudio.live2d.dialogue_placement.v1"
    assert restored_clip.dialogue_motion_payload["schema"] == "tigerstudio.live2d.dialogue_motion.v1"


def test_tts_sidecar_ensure_reports_running_without_start(monkeypatch):
    import app.tts_setup as tts_setup
    import app.tts_sidecar_runtime as runtime

    monkeypatch.setattr(
        tts_setup,
        "tts_provider_status",
        lambda env=None: {
            **_ready_zoe_status(),
            "installed": True,
            "endpoint": "http://127.0.0.1:5999",
        },
    )
    monkeypatch.setattr(
        runtime,
        "tts_endpoint_health",
        lambda endpoint, timeout_s=0.5: {"running": True, "endpoint": endpoint, "route": "status", "error": ""},
    )

    result = runtime.ensure_tts_sidecar_running(auto_start=True)

    assert result["ready"] is True
    assert result["started"] is False
    assert result["message"] == "TTS server is already running."


def test_tts_voice_lab_qa_success_message_does_not_claim_not_ready(monkeypatch):
    from tools import qa_tts_voice_lab

    monkeypatch.setattr(
        qa_tts_voice_lab,
        "tts_setup_view_model",
        lambda: {"ready": True},
    )
    monkeypatch.setattr(
        qa_tts_voice_lab,
        "ensure_tts_sidecar_running",
        lambda **_kwargs: {
            "ready": True,
            "running": True,
            "started": False,
            "message": "TTS server is already running.",
            "error": "",
        },
    )

    report = qa_tts_voice_lab.build_voice_lab_qa_report()

    assert report["ok"] is True
    assert report["failures"] == []
    assert report["user_message"] == "TTS server is already running."


def test_tts_sidecar_ensure_auto_starts_and_waits(monkeypatch):
    import app.tts_setup as tts_setup
    import app.tts_sidecar_runtime as runtime

    probes = iter(
        [
            {"running": False, "endpoint": "http://127.0.0.1:5999", "error": "offline"},
            {"running": True, "endpoint": "http://127.0.0.1:5999", "route": "models/info", "error": ""},
        ]
    )
    monkeypatch.setattr(
        tts_setup,
        "tts_provider_status",
        lambda env=None: {
            **_ready_zoe_status(),
            "installed": True,
            "endpoint": "http://127.0.0.1:5999",
        },
    )
    monkeypatch.setattr(runtime, "tts_endpoint_health", lambda endpoint, timeout_s=0.5: next(probes))
    monkeypatch.setattr(
        runtime,
        "start_tts_sidecar",
        lambda env=None: {"started": True, "pid": 1234, "endpoint": "http://127.0.0.1:5999", "error": ""},
    )
    monkeypatch.setattr(runtime.time, "sleep", lambda _seconds: None)

    result = runtime.ensure_tts_sidecar_running(auto_start=True, wait_timeout_s=2)

    assert result["ready"] is True
    assert result["started"] is True
    assert result["launch"]["pid"] == 1234


def test_tts_sidecar_ensure_offline_includes_user_guidance(monkeypatch):
    import app.tts_setup as tts_setup
    import app.tts_sidecar_runtime as runtime

    monkeypatch.setattr(
        tts_setup,
        "tts_provider_status",
        lambda env=None: {
            **_ready_zoe_status(),
            "installed": True,
            "endpoint": "http://127.0.0.1:5999",
        },
    )
    monkeypatch.setattr(
        runtime,
        "tts_endpoint_health",
        lambda endpoint, timeout_s=0.5: {
            "running": False,
            "endpoint": endpoint,
            "error": "connection refused",
        },
    )

    result = runtime.ensure_tts_sidecar_running(auto_start=False)

    assert result["ready"] is False
    assert result["guidance"]["schema"] == "tigercapture.tts_sidecar.guidance.v1"
    assert "Press Start server" in result["message"]
    assert "connection refused" in result["message"]


def test_tts_sidecar_ensure_missing_install_includes_recovery_actions(monkeypatch):
    import app.tts_setup as tts_setup
    import app.tts_sidecar_runtime as runtime

    monkeypatch.setattr(
        tts_setup,
        "tts_provider_status",
        lambda env=None: {
            "provider_id": "style_bert_vits2_sidecar",
            "installed": False,
            "available": False,
            "endpoint": "http://127.0.0.1:5999",
            "root": {
                "root": "D:/missing/Style-Bert-VITS2",
                "exists": False,
                "valid": False,
                "missing": ["root"],
            },
            "reason": "Style-Bert-VITS2 sidecar is not installed or not connected.",
        },
    )

    result = runtime.ensure_tts_sidecar_running(auto_start=True)

    assert result["ready"] is False
    assert result["started"] is False
    assert result["guidance"]["state"] == "provider_not_ready"
    assert result["guidance"]["schema"] == "tigercapture.tts_sidecar.guidance.v1"
    assert "Connect an existing Style-Bert-VITS2 folder" in result["message"]
    action_ids = {row["id"] for row in result["guidance"]["actions"]}
    assert {"tts.connect_installed_sidecar", "tts.install.plan", "tts.setup.view"} <= action_ids


def test_tts_sidecar_ensure_start_failure_includes_start_plan(monkeypatch):
    import app.tts_setup as tts_setup
    import app.tts_sidecar_runtime as runtime

    monkeypatch.setattr(
        tts_setup,
        "tts_provider_status",
        lambda env=None: {
            **_ready_zoe_status(),
            "installed": True,
            "available": True,
            "endpoint": "http://127.0.0.1:5999",
            "root": {
                "root": "D:/TTS/sbv2/Style-Bert-VITS2",
                "valid": True,
                "model_names": ["zoe"],
            },
        },
    )
    monkeypatch.setattr(
        runtime,
        "tts_endpoint_health",
        lambda endpoint, timeout_s=0.5: {
            "running": False,
            "endpoint": endpoint,
            "error": "connection refused",
        },
    )
    monkeypatch.setattr(
        runtime,
        "start_tts_sidecar",
        lambda env=None: {
            "started": False,
            "endpoint": "http://127.0.0.1:5999",
            "error": "CreateProcess failed",
            "command": ["python.exe", "server_fastapi.py"],
        },
    )

    result = runtime.ensure_tts_sidecar_running(auto_start=True)

    assert result["ready"] is False
    assert result["guidance"]["state"] == "start_failed"
    assert "could not start the TTS server" in result["message"]
    assert "CreateProcess failed" in result["message"]
    assert any(row["id"] == "tts.server.start_plan" for row in result["guidance"]["actions"])


def test_tts_generate_action_reports_startup_guidance(monkeypatch, tmp_path):
    from app.actions import build_default_action_registry
    import app.tts_setup as tts_setup
    import app.tts_sidecar_runtime as runtime

    monkeypatch.setattr(
        tts_setup,
        "tts_provider_status",
        lambda: {
            **_ready_zoe_status(),
            "installed": True,
            "available": True,
            "endpoint": "http://127.0.0.1:5999",
        },
    )
    guidance = runtime.tts_sidecar_failure_guidance(
        "startup_timeout",
        endpoint="http://127.0.0.1:5999",
        raw_error="models/info timeout",
    )
    monkeypatch.setattr(
        runtime,
        "ensure_tts_sidecar_running",
        lambda **_kwargs: {
            "ready": False,
            "running": False,
            "started": True,
            "endpoint": "http://127.0.0.1:5999",
            "guidance": guidance,
            "message": runtime.format_tts_sidecar_guidance(guidance),
            "error": "startup timed out",
        },
    )

    owner = _TtsOwner()
    registry = build_default_action_registry(owner)
    result = registry.execute(
        "tts.subtitle.generate_to_timeline",
        {
            "output_dir": str(tmp_path / "tts"),
            "track_name": "ZOE Dialogue",
            "auto_start_server": True,
        },
    ).to_dict()

    assert result["ok"] is False
    assert "Voice Lab TTS server did not become ready" in result["error"]
    assert "Next steps:" in result["error"]
    assert "models/info timeout" in result["error"]
