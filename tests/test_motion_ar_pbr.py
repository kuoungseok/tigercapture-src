from pathlib import Path

import numpy as np

from app.motion_designer.ar_pbr_source import (
    create_ar_pbr_layer,
    create_camera_layer,
    create_light_layer,
    evaluate_ar_pbr_frame,
    set_depth_group,
)
from app.motion_designer.schema import AnimatedProperty, Keyframe, MotionComposition


def _asset() -> Path:
    return Path("sample_assets/pbr_blender_scenes/polyhaven/models/Camera_01/Camera_01_1k.gltf").resolve()


def test_ar_pbr_camera_light_material_and_depth_are_evaluated_in_composition_time(tmp_path) -> None:
    composition = MotionComposition(width=640, height=360, duration_ms=2000)
    model = create_ar_pbr_layer(_asset(), width=640, height=360, duration_ms=2000)
    camera = create_camera_layer(duration_ms=2000)
    light = create_light_layer(duration_ms=2000)
    camera.source.params["fov"] = AnimatedProperty(
        default=45.0,
        keyframes=[Keyframe(time_ms=0, value=45.0), Keyframe(time_ms=1000, value=90.0)],
    ).to_dict()
    camera.source.params["rotation"] = AnimatedProperty(
        value_type="vector3", default=[0.0, 0.0, 0.0],
        keyframes=[Keyframe(time_ms=0, value=[0, 0, 0]), Keyframe(time_ms=1000, value=[10, 20, 0])],
    ).to_dict()
    light.source.params["color"] = AnimatedProperty(
        value_type="color3", default=[1.0, 1.0, 1.0],
        keyframes=[Keyframe(time_ms=0, value=[1, 1, 1]), Keyframe(time_ms=1000, value=[1, .4, .2])],
    ).to_dict()
    light.source.params["intensity"] = AnimatedProperty(
        default=.4, keyframes=[Keyframe(time_ms=0, value=.4), Keyframe(time_ms=1000, value=1.2)],
    ).to_dict()
    model.source.params["material"]["override_strength"] = AnimatedProperty(default=1.0).to_dict()
    model.source.params["material"]["metallic"] = AnimatedProperty(default=.75).to_dict()
    depth_path = tmp_path / "depth.npy"
    np.save(depth_path, np.full((360, 640), .6, dtype=np.float32))
    composition.layers = [model, camera, light]
    group = set_depth_group(
        composition, member_layer_ids=[model.id], depth_source_id="depth_a",
        depth_frame_path=str(depth_path), occlusion=True,
    )

    frame = evaluate_ar_pbr_frame(model, 500, composition=composition, composition_time_ms=500)

    assert frame.track["material_override"] is True
    assert frame.track["render"]["lighting"]["surface_metallic"] == .75
    assert frame.track["transform"]["rotation"] == [-5.0, 8.0, 0.0]
    assert frame.settings["model_view"]["fov_deg"] == 67.5
    assert frame.settings["model_view"]["auto_fit"] is True
    assert frame.track["render"]["lighting"]["light_color"] == [1.0, .7, .6]
    assert frame.track["render"]["lighting"]["direct_strength"] == .8
    assert frame.track["occlusion"] is True
    assert frame.depth_frame == str(depth_path.resolve())
    assert frame.diagnostics["depth_group_id"] == group["id"]


def test_ar_pbr_adapter_uses_existing_compositor_for_preview_and_export(monkeypatch) -> None:
    from app.motion_designer.adapters import ar_pbr as adapter

    composition = MotionComposition(width=64, height=36, duration_ms=1000)
    layer = create_ar_pbr_layer(_asset(), width=64, height=36, duration_ms=1000)
    composition.layers = [layer]
    calls = []

    def fake_render(base, time_ms, ar_tracks, camera_solution, depth_frame=None, settings=None):
        calls.append((time_ms, settings["renderer"]))
        output = np.asarray(base).copy()
        output[4:12, 5:14] = [255, 80, 20, 255]
        return output, {"ok": True, "mode": "full_model_view_gpu_export_service", "fallback": False}

    monkeypatch.setattr(adapter, "composite_preview_frame", fake_render)
    monkeypatch.setattr(adapter, "composite_export_frame", fake_render)
    adapter.clear_ar_pbr_cache()
    preview = adapter.render_ar_pbr(layer, 250, composition=composition, composition_time_ms=250, quality="preview")
    exported = adapter.render_ar_pbr(layer, 250, composition=composition, composition_time_ms=250, quality="export")

    assert preview.width() == exported.width() == 64
    assert preview.height() == exported.height() == 36
    assert len(calls) == 2
    assert all(renderer == "full_gpu" for _time, renderer in calls)
    assert adapter.ar_pbr_diagnostics(layer.id)["source_adapter"] == "motion_ar_pbr_existing_opengl_service"
