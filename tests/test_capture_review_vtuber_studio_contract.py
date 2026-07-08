from pathlib import Path

import pytest
from PIL import Image

from tools import capture_review_vtuber_studio as capture


def test_load_avatar_visual_rejects_face_thumbnail_when_product_render_fails(monkeypatch):
    def fail_render(*_args, **_kwargs):
        raise RuntimeError("render failed")

    monkeypatch.setattr(capture, "_render_avatar", fail_render)

    with pytest.raises(RuntimeError, match="upper-body avatar render"):
        capture._load_avatar_visual(Path("Milica_v1.3.vrm"))


def test_debug_face_thumbnail_fallback_is_marked_invalid(monkeypatch):
    def fail_render(*_args, **_kwargs):
        raise RuntimeError("render failed")

    def fake_thumbnail(_path):
        return Image.new("RGBA", (32, 32), (255, 255, 255, 255)), {
            "visual_source": "vrm_meta_thumbnail_texture",
            "renderer_family": "vtuber_vrm",
            "render_profile": "vrm_mtoon",
        }

    monkeypatch.setattr(capture, "_render_avatar", fail_render)
    monkeypatch.setattr(capture, "_load_vrm_meta_thumbnail", fake_thumbnail)

    _image, diagnostics = capture._load_avatar_visual(
        Path("Milica_v1.3.vrm"),
        allow_face_thumbnail_fallback=True,
    )
    contract = capture._avatar_evidence_contract(diagnostics)

    assert contract["review_product_evidence"] is False
    assert contract["visual_source"] == "vrm_meta_thumbnail_texture"
    assert contract["visible_parts"] == []
    assert contract["framing_contract"] == "violates_upper_body_rule_face_thumbnail_only"


def test_upper_body_render_contract_records_required_visible_parts(monkeypatch):
    def fake_render(_path, *, time_ms):
        assert time_ms == 12000
        return Image.new("RGBA", (32, 64), (255, 255, 255, 255)), {
            "ok": True,
            "renderer_family": "vtuber_vrm",
            "render_profile": "vrm_mtoon",
            "renderer": "vrm_mtoon_gpu",
            "requested_renderer": "vrm_mtoon_gpu",
            "pbr_renderer": False,
            "ar_pbr_preview": False,
        }

    monkeypatch.setattr(capture, "_render_avatar", fake_render)

    _image, diagnostics = capture._load_avatar_visual(Path("Milica_v1.3.vrm"), render_time_ms=12000)
    contract = capture._avatar_evidence_contract(diagnostics)

    assert contract["review_product_evidence"] is True
    assert contract["minimum_visible_parts"] == ["head", "neck", "shoulders", "upper_torso"]
    assert contract["visible_parts"] == ["head", "neck", "shoulders", "upper_torso"]
    assert contract["renderer_family"] == "vtuber_vrm"
    assert contract["render_profile"] == "vrm_mtoon"
    assert contract["renderer_backend"] == "vrm_mtoon_gpu"
    assert contract["gpu_renderer_required"] is True
    assert contract["gpu_renderer_used"] is True


def test_upper_body_render_rejects_software_renderer(monkeypatch):
    def fake_render(_path, *, time_ms):
        return Image.new("RGBA", (32, 64), (255, 255, 255, 255)), {
            "ok": True,
            "renderer_family": "vtuber_vrm",
            "render_profile": "vrm_mtoon",
            "renderer": "vrm_mtoon_software",
            "requested_renderer": "vrm_mtoon_software",
            "pbr_renderer": False,
            "ar_pbr_preview": False,
        }

    monkeypatch.setattr(capture, "_render_avatar", fake_render)

    with pytest.raises(RuntimeError, match="GPU renderer"):
        capture._load_avatar_visual(Path("Milica_v1.3.vrm"), render_time_ms=12000)
