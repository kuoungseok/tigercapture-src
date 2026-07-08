from __future__ import annotations

import json
from pathlib import Path


def test_animation_qa_deck_contains_expected_effects():
    from app.pptgen.animation_qa import build_animation_qa_deck
    from app.pptgen.animations import animation_payload

    deck = build_animation_qa_deck()
    effects = {
        animation_payload(element.animation)["in_animation"]
        for slide in deck.slides
        for element in slide.elements
        if animation_payload(element.animation)["in_animation"] != "none"
    }
    triggers = {
        animation_payload(element.animation)["trigger"]
        for slide in deck.slides
        for element in slide.elements
        if animation_payload(element.animation)["in_animation"] != "none"
    }

    assert {"appear", "fade_in", "fade_out", "move", "scale"}.issubset(effects)
    assert "on_click" in triggers


def test_animation_qa_outputs_manifest_and_pptx(tmp_path):
    from app.pptgen.animation_qa import write_animation_qa_outputs

    manifest = write_animation_qa_outputs(tmp_path)

    assert manifest["ok"] is True
    assert Path(manifest["paths"]["pptx"]).is_file()
    assert Path(manifest["paths"]["project"]).is_file()
    assert Path(manifest["paths"]["contact_sheet"]).is_file()
    assert Path(manifest["paths"]["manifest"]).is_file()
    assert manifest["slide_png_count"] == 4
    checks = manifest["ooxml_static_checks"]
    assert checks["slide_count"] == 4
    assert checks["slides_with_timing"] >= 3
    assert checks["anim_effect_count"] >= 5
    assert checks["on_click_count"] >= 2

    stored = json.loads(Path(manifest["paths"]["manifest"]).read_text(encoding="utf-8"))
    assert stored["schema"] == "tigercapture.ppt_animation_compat_qa.v1"
    assert stored["paths"]["pptx"] == manifest["paths"]["pptx"]


def test_libreoffice_validation_skips_when_executable_missing(monkeypatch, tmp_path):
    from app.pptgen import animation_qa

    pptx = tmp_path / "sample.pptx"
    pptx.write_bytes(b"not a real deck")
    monkeypatch.setattr(animation_qa, "find_libreoffice_executable", lambda: None)

    result = animation_qa.validate_with_libreoffice(pptx, tmp_path / "host")

    assert result["host"] == "libreoffice"
    assert result["status"] == "skipped"
    assert "not found" in result["reason"]


def test_animation_qa_manifest_can_require_passing_host(monkeypatch, tmp_path):
    from app.pptgen import animation_qa

    def fake_run_host_validation(*_args, **_kwargs):
        return {
            "requested": "libreoffice",
            "passed": True,
            "results": [{"host": "libreoffice", "status": "passed", "output_pdf": "deck.pdf"}],
        }

    monkeypatch.setattr(animation_qa, "run_host_validation", fake_run_host_validation)

    manifest = animation_qa.write_animation_qa_outputs(
        tmp_path,
        host_check="libreoffice",
        require_host=True,
    )

    assert manifest["ok"] is True
    assert manifest["host_validation"]["required"] is True
    assert manifest["host_validation"]["passed"] is True
    assert manifest["host_validation"]["results"][0]["host"] == "libreoffice"
