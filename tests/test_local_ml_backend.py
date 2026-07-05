from __future__ import annotations

import json


def _synthetic_subject_image(path):
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (240, 160), (18, 22, 34))
    draw = ImageDraw.Draw(image)
    draw.rectangle((86, 44, 178, 128), fill=(246, 96, 72))
    draw.ellipse((112, 22, 150, 64), fill=(255, 207, 112))
    image.save(path)
    return path


def test_local_ml_status_defaults_to_local_and_non_cloud():
    from app.local_ml import local_ml_backend_status

    status = local_ml_backend_status()

    assert status["mode"] == "local"
    assert "disabled" not in status
    assert status["cloud_enabled"] is False
    assert status["api_required"] is False
    assert "opencv_visual" in status["capabilities"]
    assert "whisper_transcription" in status["capabilities"]


def test_local_ml_can_be_disabled_by_env(monkeypatch):
    from app.local_ml import local_ml_backend_status

    monkeypatch.setenv("TIGERCAPTURE_LOCAL_ML_DISABLED", "1")
    status = local_ml_backend_status()

    assert status["mode"] == "disabled"
    assert status["disabled"] is True
    assert status["cloud_enabled"] is False
    assert status["reason"] == "feature_gate_disabled"


def test_local_ml_analyzes_prominent_region_image(tmp_path, monkeypatch):
    from app.local_ml import local_ml_analyze_media

    monkeypatch.setenv("TIGERCAPTURE_LOCAL_ML_ENABLED", "1")
    sample = _synthetic_subject_image(tmp_path / "subject.png")
    report = local_ml_analyze_media(sample, sample_count=1)

    assert report["ok"] is True
    assert report["mode"] == "local"
    assert report["cloud_enabled"] is False
    assert report["kind"] == "image"
    assert report["subject_detections"]
    assert "foreground_region" in report["object_tags"]
    first = report["subject_detections"][0]
    assert 0.35 <= first["x_norm"] <= 0.75
    assert 0.25 <= first["y_norm"] <= 0.85


def test_capcut_bundle_from_local_media_uses_local_analysis(tmp_path, monkeypatch):
    from app.capcut_workflow import capcut_creator_bundle_from_local_media

    monkeypatch.setenv("TIGERCAPTURE_CAPCUT_LOCAL_ML_ENABLED", "1")
    sample = _synthetic_subject_image(tmp_path / "screen_capture_demo.png")
    bundle = capcut_creator_bundle_from_local_media(sample, target_count=2, sample_count=1)

    assert bundle["ok"] is True
    assert bundle["local_ml_analysis"]["ok"] is True
    assert bundle["local_ml_analysis"]["cloud_enabled"] is False
    assert bundle["project_settings_patch"]["capcut_creator_workflow"]["enabled"] is True
    assert bundle["project_settings_patch"]["capcut_creator_workflow"]["subject_reframe"]["mode"] == "subject_aware"
    assert any("foreground_region" in chip for chip in bundle["search_chips"])


def test_local_ml_qa_tool_writes_report(tmp_path, monkeypatch):
    from tools import qa_local_ml_backend

    out = tmp_path / "local_ml_qa.json"
    monkeypatch.setattr(
        "sys.argv",
        ["qa_local_ml_backend.py", "--out", str(out)],
    )

    assert qa_local_ml_backend.main() == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["ok"] is True
    assert report["summary"]["mode"] == "local"
    assert report["summary"].get("disabled") is not True
    assert report["summary"]["cloud_enabled"] is False
    assert report["summary"]["detections"] >= 0
    assert report["checks"]["capcut_bundle"] is True
