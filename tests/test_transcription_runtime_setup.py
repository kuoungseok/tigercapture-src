from __future__ import annotations

import json


def test_transcription_runtime_setup_reports_candidate_paths_and_actions(tmp_path, monkeypatch) -> None:
    from app.transcription_runtime_setup import build_transcription_runtime_setup_report, candidate_whisper_model_paths

    monkeypatch.delenv("TIGERCAPTURE_LOCAL_WHISPER_MODEL", raising=False)
    monkeypatch.delenv("TIGERCAPTURE_LOCAL_MODEL_DIR", raising=False)
    monkeypatch.setenv("TIGERCAPTURE_TRANSCRIPTION_SETTINGS_FILE", str(tmp_path / "settings.json"))
    monkeypatch.setenv("TIGERCAPTURE_DISABLE_HF_WHISPER_CACHE_DISCOVERY", "1")

    paths = candidate_whisper_model_paths(tmp_path)
    report = build_transcription_runtime_setup_report(tmp_path)

    assert str(tmp_path / "models" / "whisper" / "small") in [str(path) for path in paths]
    assert report["ok"] is True
    assert "candidate_paths" in report
    assert report["next_actions"]


def test_transcription_runtime_setup_uses_saved_model_path(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("TIGERCAPTURE_LOCAL_WHISPER_MODEL", raising=False)
    monkeypatch.delenv("TIGERCAPTURE_LOCAL_MODEL_DIR", raising=False)
    monkeypatch.setenv("TIGERCAPTURE_TRANSCRIPTION_SETTINGS_FILE", str(tmp_path / "settings.json"))
    monkeypatch.setenv("TIGERCAPTURE_DISABLE_HF_WHISPER_CACHE_DISCOVERY", "1")

    from app.transcription_runtime_setup import build_transcription_runtime_setup_report, candidate_whisper_model_paths
    from app.transcription_settings import save_local_whisper_model_path

    model_dir = tmp_path / "fw-small"
    model_dir.mkdir()
    saved = save_local_whisper_model_path(model_dir)
    paths = candidate_whisper_model_paths(tmp_path / "project")
    report = build_transcription_runtime_setup_report(tmp_path / "project")

    assert saved["ok"] is True
    assert str(model_dir.resolve()) in [str(path) for path in paths]
    assert report["settings"]["local_whisper_model"]["path"] == str(model_dir.resolve())
    assert str(model_dir.resolve()) in report["existing_paths"]


def test_cached_huggingface_faster_whisper_model_is_candidate(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("TIGERCAPTURE_DISABLE_HF_WHISPER_CACHE_DISCOVERY", raising=False)
    monkeypatch.setenv("TIGERCAPTURE_TRANSCRIPTION_SETTINGS_FILE", str(tmp_path / "settings.json"))
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path / "hf" / "hub"))

    from app.transcription_settings import cached_faster_whisper_model_candidates

    snapshot = tmp_path / "hf" / "hub" / "models--Systran--faster-whisper-small" / "snapshots" / "abc123"
    snapshot.mkdir(parents=True)
    (snapshot / "config.json").write_text("{}", encoding="utf-8")
    (snapshot / "model.bin").write_bytes(b"model")

    candidates = cached_faster_whisper_model_candidates("small")

    assert str(snapshot.resolve()) in [str(path) for path in candidates]


def test_configure_local_whisper_model_cli_saves_path(tmp_path, monkeypatch, capsys) -> None:
    from tools import configure_local_whisper_model

    model_dir = tmp_path / "fw-small"
    model_dir.mkdir()
    out = tmp_path / "configure.json"
    monkeypatch.setenv("TIGERCAPTURE_TRANSCRIPTION_SETTINGS_FILE", str(tmp_path / "settings.json"))
    monkeypatch.setenv("TIGERCAPTURE_DISABLE_HF_WHISPER_CACHE_DISCOVERY", "1")
    monkeypatch.setattr(
        "sys.argv",
        ["configure_local_whisper_model.py", "--model-path", str(model_dir), "--out", str(out)],
    )

    assert configure_local_whisper_model.main() == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    stdout = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "transcription_settings_configure"
    assert payload["configure_result"]["ok"] is True
    assert stdout["ok"] is True


def test_transcription_runtime_setup_cli_writes_report(tmp_path, monkeypatch, capsys) -> None:
    from tools import qa_transcription_runtime_setup

    out = tmp_path / "runtime_setup.json"
    monkeypatch.setenv("TIGERCAPTURE_TRANSCRIPTION_SETTINGS_FILE", str(tmp_path / "settings.json"))
    monkeypatch.setenv("TIGERCAPTURE_DISABLE_HF_WHISPER_CACHE_DISCOVERY", "1")
    monkeypatch.setattr("sys.argv", ["qa_transcription_runtime_setup.py", "--out", str(out)])

    assert qa_transcription_runtime_setup.main() == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    stdout = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "transcription_runtime_setup"
    assert stdout["ok"] is True
