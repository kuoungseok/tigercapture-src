from __future__ import annotations

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


def test_tts_actions_are_registered_and_readable(tmp_path):
    from app.actions.registry import ActionRegistry

    registry = ActionRegistry()
    ids = {row["id"] for row in registry.list_actions()}

    assert "tts.provider.status" in ids
    assert "tts.install.plan" in ids
    assert "tts.connect_installed_sidecar" in ids
    assert "tts.server.ensure_running" in ids
    assert "tts.voice.list" in ids
    assert "tts.subtitle.plan" in ids
    assert "tts.subtitle.generate_to_timeline" in ids
    assert "tts.subtitle.apply_actor_lipsync" in ids

    result = registry.execute("tts.install.plan", {"install_root": str(tmp_path / "tts")})
    assert result.ok is True
    assert result.result["provider_id"] == "style_bert_vits2_sidecar"


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
        "root": {"model_names": ["amitaro", "zoe"]},
    }


def test_tts_subtitle_plan_prefers_user_trained_zoe(monkeypatch, tmp_path):
    from app.actions import build_default_action_registry
    import app.tts_setup as tts_setup

    monkeypatch.setattr(tts_setup, "tts_provider_status", lambda: _ready_zoe_status())
    owner = _TtsOwner()
    registry = build_default_action_registry(owner)

    result = registry.execute("tts.subtitle.plan", {"output_dir": str(tmp_path / "tts")}).to_dict()

    assert result["ok"] is True
    assert result["result"]["model_name"] == "zoe"
    assert result["result"]["subtitle_count"] == 2
    assert result["result"]["rows"][0]["start_ms"] == 1000
    assert "tts_sub_0000_" in result["result"]["rows"][0]["output_path"]


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
    assert result["result"]["model_name"] == "zoe"
    assert result["result"]["clip_count"] == 2
    assert len(owner._audio_tracks) == 1
    track = owner._audio_tracks[0]
    assert track.label == "ZOE Dialogue"
    assert track.track_type == "dialogue"
    assert [clip.offset_ms for clip in track.clips] == [1000, 3500]
    assert [clip.trim_end_ms for clip in track.clips] == [900, 901]
    assert len(owner._action_imported_media) == 2
    assert owner.changes[-1] == "Generate TTS subtitle track"


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
    assert result["result"]["parameter_tracks"] == ["ParamMouthOpenY", "ParamMouthForm"]
    assert clip.parameter_keyframes["ParamMouthOpenY"][0]["time_ms"] == 166
    assert any(row["value"] > 0.25 for row in clip.parameter_keyframes["ParamMouthOpenY"])
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
    assert owner.changes[-1] == "Generate TTS subtitle track"


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
