from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace


def test_invisible_hdri_keeps_reflection_and_diffuse_rays() -> None:
    from app.ar_pbr.render_environment import normalize_environment_visibility

    policy = normalize_environment_visibility({
        "show_environment_background": False,
        "environment_visibility": {
            "reflection_visible": True,
            "diffuse_visible": True,
            "refraction_visible": True,
        },
    })

    assert policy["camera_visible"] is False
    assert policy["background_output"] == "transparent"
    assert policy["reflection_visible"] is True
    assert policy["diffuse_visible"] is True
    assert policy["invisible_reflection_environment"] is True


def test_environment_ray_visibility_normalizes_independent_strengths() -> None:
    from app.ar_pbr.render_environment import normalize_environment_visibility

    policy = normalize_environment_visibility({
        "environment_visibility": {
            "camera_visible": False,
            "reflection_visible": True,
            "diffuse_visible": False,
            "refraction_visible": False,
            "reflection_strength": 1.7,
            "diffuse_strength": 0.4,
            "reflection_rotation": 135.0,
            "background_output": "solid",
        },
    })

    assert policy["camera_visible"] is False
    assert policy["reflection_visible"] is True
    assert policy["diffuse_visible"] is False
    assert policy["refraction_visible"] is False
    assert policy["reflection_strength"] == 1.7
    assert policy["diffuse_strength"] == 0.4
    assert policy["reflection_rotation"] == 135.0
    assert policy["background_output"] == "solid"


def test_background_output_is_authoritative_for_environment_camera_visibility() -> None:
    from app.ar_pbr.render_environment import normalize_environment_visibility

    transparent = normalize_environment_visibility({"background_output": "transparent"})
    solid = normalize_environment_visibility({"background_output": "solid"})
    environment = normalize_environment_visibility({
        "camera_visible": False,
        "background_output": "environment",
    })

    assert transparent["camera_visible"] is False
    assert solid["camera_visible"] is False
    assert environment["camera_visible"] is True


def test_rt_mode_never_claims_cuda_as_hardware_rt(monkeypatch) -> None:
    from app.ar_pbr.render_environment import hardware_rt_capability, resolve_render_mode

    monkeypatch.delenv("TIGERSTUDIO_HARDWARE_RT_HELPER", raising=False)
    capability = hardware_rt_capability()
    hybrid = resolve_render_mode({"render_mode": "hybrid_rt"}, capability=capability)
    path = resolve_render_mode({"render_mode": "path_traced"}, capability=capability)

    assert capability["available"] is False
    assert capability["cuda_is_not_rt_proof"] is True
    assert hybrid["requested"] == "hybrid_rt"
    assert hybrid["active"] == "ibl_realtime"
    assert hybrid["fallback_reason"] == "native_rt_backend_unavailable"
    assert path["active"] == "ibl_realtime"


def test_native_helper_capability_enables_hybrid_and_path_modes(tmp_path, monkeypatch) -> None:
    import app.ar_pbr.render_environment as module

    helper = tmp_path / "TigerRtHelper.exe"
    helper.write_bytes(b"probe")
    payload = {"hardware_ray_tracing": True, "api": "dxr", "device": "RTX Test"}
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr=""),
    )

    capability = module.hardware_rt_capability(helper)
    hybrid = module.resolve_render_mode({"render_mode": "hybrid_rt"}, capability=capability)
    path = module.resolve_render_mode({"render_mode": "path_traced"}, capability=capability)

    assert capability["available"] is True
    assert capability["api"] == "dxr"
    assert hybrid["active"] == "hybrid_rt"
    assert hybrid["environment_policy"] == "diffuse_ibl_rt_reflection_with_environment_miss"
    assert path["active"] == "path_traced"
    assert path["environment_policy"] == "ray_sampled_environment_no_prefilter_approximation"


def test_native_helper_capability_is_cached_off_the_render_hot_path(tmp_path, monkeypatch) -> None:
    import app.ar_pbr.render_environment as module

    helper = tmp_path / "TigerRtHelper.exe"
    helper.write_bytes(b"probe")
    calls = []

    def run(*args, **kwargs):
        calls.append(args)
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"hardware_ray_tracing": True, "api": "dxr"}),
            stderr="",
        )

    monkeypatch.setattr(module.subprocess, "run", run)
    module.hardware_rt_capability(helper, refresh=True)
    module.hardware_rt_capability(helper)
    module.resolve_render_mode(
        {"render_mode": "hybrid_rt"},
        capability=module.hardware_rt_capability(helper),
    )

    assert len(calls) == 1


def test_lighting_schema_persists_environment_and_rt_request() -> None:
    from app.ar_pbr.schema import normalize_lighting_settings

    lighting = normalize_lighting_settings({
        "render_mode": "hybrid_rt",
        "show_environment_background": False,
        "environment_visibility": {
            "camera_visible": False,
            "reflection_visible": True,
            "diffuse_visible": True,
            "background_output": "transparent",
        },
    })

    assert lighting["render_mode"] == "hybrid_rt"
    assert lighting["render_mode_policy"]["active"] == "ibl_realtime"
    assert lighting["show_environment_background"] is False
    assert lighting["environment_visibility"]["invisible_reflection_environment"] is True


def test_live_shader_has_separate_diffuse_and_reflection_environment_energy() -> None:
    import app.opengl_preview as preview

    shader = preview._AR_PBR_TEXTURE_FRAGMENT_SHADER
    assert "uniform float u_diffuse_environment_strength" in shader
    assert "uniform float u_reflection_environment_strength" in shader
    assert "u_ibl_exposure * u_diffuse_environment_strength" in shader
    assert "u_ibl_exposure * u_reflection_environment_strength" in shader


def test_rt_status_action_exposes_honest_fallback() -> None:
    from app.actions import build_default_action_registry

    registry = build_default_action_registry(None)
    payload = registry.execute(
        "ar_pbr.preview.rt_status",
        {"render_mode": "hybrid_rt"},
    ).to_dict()

    assert payload["ok"] is True
    assert payload["result"]["requested"] == "hybrid_rt"
    assert payload["result"]["hardware_rt_active"] is False
    assert payload["result"]["active"] == "ibl_realtime"


def test_rt_helper_contract_is_process_isolated_from_painter() -> None:
    source = Path("app/ar_pbr/render_environment.py").read_text(encoding="utf-8")
    assert "subprocess.run" in source
    assert "shell=True" not in source
    assert "app.painter" not in source
    assert "app.drawing" not in source
