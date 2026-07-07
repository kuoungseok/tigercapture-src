import numpy as np
from types import SimpleNamespace


def test_internal_vrm_fallback_missing_assets_returns_transparent_frame(tmp_path):
    from app.vtuber.internal_vrm_fallback import render_internal_vrm_fallback_frame

    image, diagnostics = render_internal_vrm_fallback_frame(
        {
            "id": "internal_vrm_fallback",
            "settings": {
                "avatar_vrm": str(tmp_path / "missing.vrm"),
                "descriptor_path": str(tmp_path / "missing.json"),
                "motion_csv": str(tmp_path / "missing.csv"),
            },
        },
        width=16,
        height=9,
    )

    assert image.size == (16, 9)
    assert diagnostics["ok"] is False
    assert diagnostics["requires_vseeface"] is False
    assert diagnostics["requires_virtual_camera"] is False
    assert diagnostics["renderer_family"] == "vtuber_vrm"
    assert diagnostics["render_profile"] == "vrm_mtoon"
    assert diagnostics["pbr_renderer"] is False
    assert diagnostics["ar_pbr_preview"] is False
    assert diagnostics["quality"]["broadcast_ready"] is False
    assert "render_resolution_below_720p" in diagnostics["quality"]["claim_blockers"]
    assert diagnostics["errors"] == ["missing_internal_vrm_fallback_asset"]


def test_internal_vrm_fallback_quality_policy_rewrites_pbr_aliases_to_vrm_renderer():
    from app.vtuber.internal_vrm_fallback import internal_vrm_fallback_quality_policy

    quality = internal_vrm_fallback_quality_policy(width=1920, height=1080, renderer="full-gpu", settings={"fps": 30})

    assert quality["renderer"] == "vrm_mtoon_software"
    assert quality["renderer_family"] == "vtuber_vrm"
    assert quality["render_profile"] == "vrm_mtoon"
    assert quality["pbr_renderer"] is False
    assert quality["ar_pbr_preview"] is False
    assert quality["profile"] == "preview_safe"
    assert quality["broadcast_ready"] is False
    assert "pbr_renderer_alias_rewritten_for_vrm:full-gpu" in quality["warnings"]
    assert "vrm_mtoon_gpu_renderer_not_selected" in quality["claim_blockers"]
    assert quality["frame_budget_ms"] == 1000.0 / 30.0


def test_internal_vrm_fallback_defaults_do_not_require_debugcapture_descriptor_or_motion(tmp_path, monkeypatch):
    from PIL import Image

    import app.vtuber.internal_vrm_fallback as fallback

    vrm = tmp_path / "avatar.vrm"
    vrm.write_bytes(b"glTF")
    calls = {}
    frame = SimpleNamespace(
        time_ms=0,
        yaw_deg=0.0,
        pitch_deg=0.0,
        roll_deg=0.0,
        shoulder_roll_deg=0.0,
        mouth_open=0.0,
        blink_l=0.0,
        blink_r=0.0,
    )

    class FakeRenderModule:
        @staticmethod
        def _apply_face_morphs(base_descriptor, morph_targets, selected_frame):
            assert selected_frame is frame
            return dict(base_descriptor)

    def fake_load_runtime(vrm_path, descriptor_path, motion_csv, upper_body_mode):
        calls["vrm_path"] = vrm_path
        calls["descriptor_path"] = descriptor_path
        calls["motion_csv"] = motion_csv
        calls["upper_body_mode"] = upper_body_mode
        return {
            "module": FakeRenderModule,
            "frames": (frame,),
            "base_descriptor": {"id": "fake_vrm"},
            "morph_targets": {},
            "descriptor_source": "vrm_import",
            "motion_source": "idle_internal_motion",
        }

    def fake_render_descriptor_frame(module, *, width, height, renderer, **_kwargs):
        assert renderer == "vrm_mtoon_software"
        return Image.new("RGBA", (width, height), (10, 20, 30, 255)), {"ok": True}

    monkeypatch.setattr(fallback, "_load_cached_runtime", fake_load_runtime)
    monkeypatch.setattr(fallback, "_render_descriptor_frame", fake_render_descriptor_frame)

    image, diagnostics = fallback.render_internal_vrm_fallback_frame(
        {"id": "internal_vrm_fallback", "settings": {"avatar_vrm": str(vrm)}},
        width=16,
        height=9,
    )

    assert image.size == (16, 9)
    assert diagnostics["ok"] is True
    assert diagnostics["descriptor"] == ""
    assert diagnostics["motion_csv"] == ""
    assert diagnostics["descriptor_source"] == "vrm_import"
    assert diagnostics["motion_source"] == "idle_internal_motion"
    assert diagnostics["renderer"] == "vrm_mtoon_software"
    assert diagnostics["renderer_family"] == "vtuber_vrm"
    assert diagnostics["render_profile"] == "vrm_mtoon"
    assert diagnostics["pbr_renderer"] is False
    assert diagnostics["ar_pbr_preview"] is False
    assert calls["descriptor_path"] == ""
    assert calls["motion_csv"] == ""


def test_vrm_renderer_contract_blocks_pbr_and_ar_pbr_aliases():
    from app.vtuber.vrm_renderer import (
        make_vrm_render_track,
        normalize_vrm_renderer,
        vrm_renderer_contract,
    )

    assert normalize_vrm_renderer("marmoset_pbr") == "vrm_mtoon_software"
    assert normalize_vrm_renderer("full_gpu") == "vrm_mtoon_software"
    contract = vrm_renderer_contract("ar_pbr")

    assert contract["family"] == "vtuber_vrm"
    assert contract["renderer"] == "vrm_mtoon_software"
    assert contract["render_profile"] == "vrm_mtoon"
    assert contract["pbr_renderer"] is False
    assert contract["ar_pbr_preview"] is False

    track = make_vrm_render_track(
        track_id="avatar",
        asset_path="C:/avatars/Milica.vrm",
        transform={"position": [0, 0, 0], "rotation": [0, 180, 0], "scale": [1, 1, 1]},
        render={"renderer": "software_pbr"},
    )

    assert track["type"] == "vrm_avatar"
    assert track["renderer_family"] == "vtuber_vrm"
    assert track["render_profile"] == "vrm_mtoon"
    assert track["render"]["renderer"] == "vrm_mtoon_software"
    assert track["render"]["pbr_enabled"] is False
    assert track["render"]["ar_pbr_preview"] is False


def test_internal_vrm_fallback_composite_suppresses_black_vseeface_source():
    from app.vtuber.internal_vrm_fallback import composite_internal_vrm_fallback_program_frame

    scene = {
        "id": "vseeface_bridge_scene",
        "canvas": {"width": 4, "height": 4, "background": [0, 255, 0, 255]},
        "sources": [
            {"id": "background", "type": "color", "z_index": 0, "settings": {"color": [0, 255, 0, 255]}},
            {
                "id": "internal_vrm_fallback",
                "type": "internal_vrm",
                "z_index": 9,
                "transform": {"x": 0, "y": 0, "width": 4, "height": 4, "fit": "stretch"},
                "settings": {"program_output": True},
            },
            {
                "id": "vseeface",
                "type": "vseeface",
                "z_index": 10,
                "transform": {"x": 0, "y": 0, "width": 4, "height": 4, "fit": "stretch"},
                "settings": {"suppress_black_frame": True},
            },
        ],
    }
    fallback = np.zeros((4, 4, 4), dtype=np.uint8)
    fallback[:, :] = [220, 80, 40, 255]
    black = np.zeros((4, 4, 3), dtype=np.uint8)

    out, diagnostics = composite_internal_vrm_fallback_program_frame(scene, fallback, vseeface_frame=black)

    assert out[1, 1, :3].tolist() == [220, 80, 40]
    rows = {row["id"]: row for row in diagnostics["sources"]}
    assert rows["internal_vrm_fallback"]["rendered"] is True
    assert rows["vseeface"]["rendered"] is False
    assert rows["vseeface"]["suppressed_black_frame"] is True
