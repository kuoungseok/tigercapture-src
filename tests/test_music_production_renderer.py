from __future__ import annotations

import json
import sys
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import music_production_renderer as renderer  # noqa: E402


def _request(tmp_path: Path) -> Path:
    row = {
        "schema": "tigerstudio.music.composition.v1",
        "composition": {
            "id": "music_test",
            "prompt": "modern melodic EDM cue",
            "genre": "melodic EDM",
            "mood": "uplifting",
            "bpm": 128,
            "key": "A minor",
            "duration_ms": 12000,
            "sections": [
                {"name": "intro", "start_ms": 0, "duration_ms": 6000, "intensity": 0.4, "chord_progression": ["Am", "F", "C", "G"]},
                {"name": "drop", "start_ms": 6000, "duration_ms": 6000, "intensity": 0.9, "chord_progression": ["Am", "F", "C", "G"]},
            ],
            "tracks": [
                {
                    "id": "drums",
                    "role": "drums",
                    "instrument": "Drums",
                    "volume": 0.8,
                    "pan": 0,
                    "clips": [{"id": "drums_intro", "section_name": "intro", "start_ms": 0, "duration_ms": 6000, "notes": []}],
                },
                {
                    "id": "bass",
                    "role": "bass",
                    "instrument": "Bass",
                    "volume": 0.7,
                    "pan": 0,
                    "clips": [{"id": "bass_intro", "section_name": "intro", "start_ms": 0, "duration_ms": 6000, "notes": []}],
                },
            ],
        },
    }
    path = tmp_path / "request.json"
    path.write_text(json.dumps(row), encoding="utf-8")
    return path


def _config(tmp_path: Path, *, strict: bool = False) -> Path:
    path = tmp_path / "provider.json"
    path.write_text(
        json.dumps(
            {
                "preferred_provider": "auto",
                "strict": strict,
                "providers": {
                    "acestep_api": {
                        "enabled": True,
                        "base_url": "http://127.0.0.1:8001",
                        "audio_format": "wav",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def test_ai_music_prompt_carries_timing_and_arrangement_context(tmp_path: Path) -> None:
    row = json.loads(_request(tmp_path).read_text(encoding="utf-8"))

    prompt = renderer.build_ai_music_prompt(row["composition"])

    assert "128 BPM" in prompt
    assert "key A minor" in prompt
    assert "12 seconds" in prompt
    assert "intro" in prompt
    assert "Am-F-C-G" in prompt
    assert "drums" in prompt


def test_production_router_uses_acestep_when_api_is_healthy(tmp_path: Path, monkeypatch) -> None:
    request = _request(tmp_path)
    output = tmp_path / "ai.wav"
    config = _config(tmp_path)

    monkeypatch.setattr(renderer, "_ace_health", lambda _config: True)

    def fake_acestep(_request_row, output_wav, _config):
        output_wav.write_bytes(b"RIFF\x00\x00\x00\x00WAVE")
        return {
            "provider": "acestep_api",
            "provider_engine": "acestep-v15-turbo",
            "fallback_used": False,
        }

    monkeypatch.setattr(renderer, "render_acestep_api", fake_acestep)

    meta = renderer.render_production_music(request, output, config_path=config)

    assert output.exists()
    assert meta["provider"] == "acestep_api"
    assert meta["fallback_used"] is False
    sidecar = json.loads(output.with_suffix(output.suffix + ".renderer.json").read_text(encoding="utf-8"))
    assert sidecar["provider"] == "acestep_api"


def test_production_router_uses_stable_audio_when_requested(tmp_path: Path, monkeypatch) -> None:
    request = _request(tmp_path)
    output = tmp_path / "stable.wav"
    config = tmp_path / "provider.json"
    config.write_text(
        json.dumps(
            {
                "preferred_provider": "stable_audio_3",
                "strict": True,
                "providers": {
                    "stable_audio_3": {
                        "enabled": True,
                        "mode": "huggingface_space",
                        "space": "stabilityai/stable-audio-3",
                        "variant_key": "small-music",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    def fake_stable(_request_row, output_wav, _config):
        output_wav.write_bytes(b"RIFF\x00\x00\x00\x00WAVE")
        return {
            "provider": "stable_audio_3",
            "provider_engine": "Stable Audio 3.0 HF Space/small-music",
            "fallback_used": False,
        }

    monkeypatch.setattr(renderer, "render_stable_audio_3_hf_space", fake_stable)

    meta = renderer.render_production_music(request, output, config_path=config)

    assert output.exists()
    assert meta["provider"] == "stable_audio_3"
    assert meta["fallback_used"] is False
    sidecar = json.loads(output.with_suffix(output.suffix + ".renderer.json").read_text(encoding="utf-8"))
    assert sidecar["provider"] == "stable_audio_3"


def test_production_router_explicit_stable_audio_overrides_disabled_default(tmp_path: Path, monkeypatch) -> None:
    request = _request(tmp_path)
    output = tmp_path / "stable_forced.wav"
    config = tmp_path / "provider.json"
    config.write_text(
        json.dumps(
            {
                "preferred_provider": "auto",
                "providers": {
                    "stable_audio_3": {
                        "enabled": False,
                        "mode": "huggingface_space",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    def fake_stable(_request_row, output_wav, _config):
        output_wav.write_bytes(b"RIFF\x00\x00\x00\x00WAVE")
        return {
            "provider": "stable_audio_3",
            "provider_engine": "Stable Audio 3.0 HF Space/small-music",
            "fallback_used": False,
        }

    monkeypatch.setenv("TIGERCAPTURE_MUSIC_AI_PROVIDER", "stable_audio_3")
    monkeypatch.setattr(renderer, "render_stable_audio_3_hf_space", fake_stable)

    meta = renderer.render_production_music(request, output, config_path=config)

    assert output.exists()
    assert meta["provider"] == "stable_audio_3"


def test_production_router_falls_back_to_lmms_when_acestep_is_unavailable(tmp_path: Path, monkeypatch) -> None:
    request = _request(tmp_path)
    output = tmp_path / "fallback.wav"
    config = _config(tmp_path)

    monkeypatch.setattr(renderer, "_ace_health", lambda _config: False)

    def fake_lmms(_composition_json, output_wav, *, keep_project=None):
        output_wav.write_bytes(b"RIFF\x00\x00\x00\x00WAVE")
        return output_wav

    monkeypatch.setattr(renderer, "render_with_lmms", fake_lmms)

    meta = renderer.render_production_music(request, output, config_path=config)

    assert output.exists()
    assert meta["provider"] == "lmms"
    assert meta["fallback_used"] is True
    assert "not healthy" in meta["fallback_reason"]
