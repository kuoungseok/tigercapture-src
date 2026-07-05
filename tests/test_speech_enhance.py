from __future__ import annotations

import json


def test_speech_enhance_plan_is_reviewable_and_local_first() -> None:
    from app.speech_enhance import build_speech_enhance_plan, synthetic_speech_enhance_qa

    plan = build_speech_enhance_plan(clip_id="clip_1", start_ms=100, end_ms=2400)
    qa = synthetic_speech_enhance_qa()

    assert plan.requires_review is True
    assert plan.operations[0].type == "apply_preset"
    assert plan.operations[0].params["effect_chain"]["voice_isolation"]["enabled"] is True
    assert plan.metadata["cloud_required"] is False
    assert qa["ok"] is True
    assert qa["snr_improvement_db"] >= 3.0


def test_speech_enhance_cli_writes_report(tmp_path, monkeypatch, capsys) -> None:
    from tools import qa_speech_enhance

    out = tmp_path / "speech_enhance.json"
    monkeypatch.setattr("sys.argv", ["qa_speech_enhance.py", "--out", str(out)])

    assert qa_speech_enhance.main() == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    stdout = json.loads(capsys.readouterr().out)
    assert payload["studio_sound_contract_ready"] is True
    assert stdout["ok"] is True
