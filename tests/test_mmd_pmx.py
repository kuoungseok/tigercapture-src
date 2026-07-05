from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import json
import math
import struct

import numpy as np
import pytest

from app.mmd.animation import evaluate_model_pose
from app.mmd.diagnostics import analyze_mmd_model, format_mmd_performance_line, format_mmd_report
from app.mmd.framing import auto_frame_bounds, bounds_from_min_max, bounds_from_positions
from app.mmd.gpu_preview import (
    MMD_MATERIAL_DEFAULT,
    MMD_MATERIAL_EMISSIVE,
    MMD_MATERIAL_EYE,
    MMD_MATERIAL_HAIR,
    MMD_MATERIAL_LIP,
    MMD_MATERIAL_METAL,
    MMD_MATERIAL_SKIN,
    MMD_MATERIAL_STOCKING,
    MMD_MATERIAL_TRANSPARENT,
    MMD_RENDER_BUCKET_CUTOUT,
    MMD_RENDER_BUCKET_OPAQUE,
    MMD_RENDER_BUCKET_TRANSPARENT,
    MMD_RENDER_TOON,
    build_mmd_render_item,
)
from app.mmd.lighting import resolve_mmd_lighting
from app.mmd.loader import load_mmd_model
from app.mmd.pmd import load_pmd
from app.mmd.pmx import MMDBone, MMDIK, MMDIKLink, MMDJoint, MMDMorph, MMDRigidBody, MMDVertexMorph, load_pmx
from app.mmd.physics import (
    SECONDARY_ROTATION_HINT_SCALE,
    SPRING_PHYSICS_RESPONSE,
    DecimatedPhysicsBackend,
    MMDPhysicsPoseDelta,
    NoPhysicsBackend,
    PyBulletPhysicsBackend,
    SpringPhysicsBackend,
    configure_mmd_physics_backend,
    create_mmd_physics_backend,
    mmd_physics_backend_diagnostics,
)
from app.mmd.regression_profiles import (
    evaluate_mmd_regression_profile,
    mmd_regression_profile,
    mmd_regression_profile_model_path,
    mmd_regression_profile_motion_path,
)
from app.mmd.vmd import (
    VMDBezier,
    VMDCameraFrame,
    VMDCameraInterpolation,
    VMDMotion,
    bone_pose_at,
    camera_at,
    load_vmd,
    morph_weights_at,
    vmd_bezier_is_linear,
    vmd_bezier_max_linear_delta,
    vmd_bezier_value,
)


def _s(text: str) -> bytes:
    raw = text.encode("utf-8")
    return struct.pack("<i", len(raw)) + raw


def _idx(value: int) -> bytes:
    return struct.pack("<i", value)


def _minimal_pmx() -> bytes:
    out = bytearray()
    out += b"PMX "
    out += struct.pack("<f", 2.0)
    out += bytes([8, 1, 0, 4, 4, 4, 4, 4, 4])
    out += _s("Tiny")
    out += _s("Tiny")
    out += _s("")
    out += _s("")
    out += struct.pack("<i", 3)
    vertices = [
        ((-1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, 0.0)),
        ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0)),
        ((0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (0.5, 1.0)),
    ]
    for pos, normal, uv in vertices:
        out += struct.pack("<3f3f2f", *pos, *normal, *uv)
        out += bytes([0])
        out += _idx(0)
        out += struct.pack("<f", 1.0)
    out += struct.pack("<i", 3)
    out += _idx(0) + _idx(1) + _idx(2)
    out += struct.pack("<i", 0)
    out += struct.pack("<i", 1)
    out += _s("mat") + _s("mat")
    out += struct.pack("<4f", 0.8, 0.7, 0.6, 1.0)
    out += struct.pack("<3f", 0.2, 0.2, 0.2)
    out += struct.pack("<f", 8.0)
    out += struct.pack("<3f", 0.25, 0.25, 0.25)
    out += bytes([0])
    out += struct.pack("<4f", 0.0, 0.0, 0.0, 1.0)
    out += struct.pack("<f", 1.0)
    out += _idx(-1)
    out += _idx(-1)
    out += bytes([0, 1, -1 & 0xFF])
    out += _s("")
    out += struct.pack("<i", 3)
    out += struct.pack("<i", 1)
    out += _s("root") + _s("root")
    out += struct.pack("<3f", 0.0, 0.0, 0.0)
    out += _idx(-1)
    out += struct.pack("<i", 0)
    out += struct.pack("<H", 0)
    out += struct.pack("<3f", 0.0, 1.0, 0.0)
    out += struct.pack("<i", 0)
    out += struct.pack("<i", 0)
    out += struct.pack("<i", 1)
    out += _s("rb") + _s("rb")
    out += _idx(0)
    out += bytes([0])
    out += struct.pack("<H", 0)
    out += bytes([0])
    out += struct.pack("<3f3f3f", 0.5, 0.5, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    out += struct.pack("<5f", 1.0, 0.25, 0.25, 0.0, 0.5)
    out += bytes([1])
    out += struct.pack("<i", 1)
    out += _s("joint") + _s("joint")
    out += bytes([0])
    out += _idx(0)
    out += _idx(-1)
    out += struct.pack("<3f3f", 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    out += struct.pack("<3f3f3f3f3f3f", *(0.0,) * 18)
    return bytes(out)


def _minimal_pmd() -> bytes:
    out = bytearray()
    out += b"Pmd"
    out += struct.pack("<f", 1.0)
    out += _fixed_text("TinyPMD", 20)
    out += _fixed_text("Tiny PMD test", 256)
    out += struct.pack("<i", 3)
    vertices = [
        ((-1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, 0.0)),
        ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0)),
        ((0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (0.5, 1.0)),
    ]
    for pos, normal, uv in vertices:
        out += struct.pack("<3f3f2f", *pos, *normal, *uv)
        out += struct.pack("<HHBB", 0, 0xFFFF, 100, 0)
    out += struct.pack("<i3H", 3, 0, 1, 2)
    out += struct.pack("<i", 1)
    out += struct.pack("<4f", 0.8, 0.7, 0.6, 1.0)
    out += struct.pack("<f", 8.0)
    out += struct.pack("<3f", 0.2, 0.2, 0.2)
    out += struct.pack("<3f", 0.25, 0.25, 0.25)
    out += struct.pack("<BBI", 0, 1, 3)
    out += _fixed_text("", 20)
    out += struct.pack("<H", 1)
    out += _fixed_text("root", 20)
    out += struct.pack("<HHBH3f", 0xFFFF, 0xFFFF, 0, 0xFFFF, 0.0, 0.0, 0.0)
    out += struct.pack("<H", 0)
    out += struct.pack("<H", 0)
    out += bytes([0])
    out += bytes([0])
    out += struct.pack("<I", 0)
    out += bytes([0])
    out += b"".join(_fixed_text(f"toon{i + 1:02d}.bmp", 100) for i in range(10))
    out += struct.pack("<I", 1)
    out += _fixed_text("rb", 20)
    out += struct.pack("<H", 0)
    out += struct.pack("<BH", 0, 0)
    out += struct.pack("<B", 0)
    out += struct.pack("<3f3f3f", 0.5, 0.5, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    out += struct.pack("<5fB", 1.0, 0.25, 0.25, 0.0, 0.5, 1)
    out += struct.pack("<I", 1)
    out += _fixed_text("joint", 20)
    out += struct.pack("<II", 0, 0)
    out += struct.pack("<3f3f", 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    out += struct.pack("<3f3f3f3f3f3f", *(0.0,) * 18)
    return bytes(out)


def _fixed_text(text: str, size: int) -> bytes:
    raw = text.encode("cp932")
    return raw[:size].ljust(size, b"\x00")


def _minimal_vmd() -> bytes:
    out = bytearray()
    out += _fixed_text("Vocaloid Motion Data 0002", 30)
    out += _fixed_text("Tiny", 20)
    out += struct.pack("<I", 1)
    out += _fixed_text("root", 15)
    out += struct.pack("<I", 15)
    out += struct.pack("<3f", 0.0, 1.0, 0.0)
    out += struct.pack("<4f", 0.0, 0.0, 0.0, 1.0)
    out += bytes(64)
    out += struct.pack("<I", 1)
    out += _fixed_text("smile", 15)
    out += struct.pack("<If", 12, 0.75)
    out += struct.pack("<I", 1)
    out += struct.pack("<If3f3f", 30, -35.0, 1.0, 2.0, 3.0, 0.1, 0.2, 0.3)
    out += bytes(24)
    out += struct.pack("<IB", 42, 0)
    return bytes(out)


def _minimal_pbx_json() -> dict:
    return {
        "metadata": {
            "format": "pmx",
            "version": 2,
            "encoding": 1,
            "modelName": "TinyPBX",
            "englishModelName": "TinyPBX",
        },
        "vertices": [
            {
                "position": [-1.0, 0.0, 0.0],
                "normal": [0.0, 0.0, 1.0],
                "uv": [0.0, 0.0],
                "type": 0,
                "skinIndices": [0],
                "skinWeights": [1.0],
                "edgeRatio": 1.0,
            },
            {
                "position": [1.0, 0.0, 0.0],
                "normal": [0.0, 0.0, 1.0],
                "uv": [1.0, 0.0],
                "type": 0,
                "skinIndices": [0],
                "skinWeights": [1.0],
                "edgeRatio": 1.0,
            },
            {
                "position": [0.0, 1.0, 0.0],
                "normal": [0.0, 0.0, 1.0],
                "uv": [0.5, 1.0],
                "type": 0,
                "skinIndices": [0],
                "skinWeights": [1.0],
                "edgeRatio": 1.0,
            },
        ],
        "faces": [{"indices": [0, 1, 2]}],
        "textures": [],
        "materials": [
            {
                "name": "mat",
                "englishName": "mat",
                "diffuse": [0.8, 0.7, 0.6, 1.0],
                "specular": [0.2, 0.2, 0.2],
                "shininess": 8.0,
                "ambient": [0.25, 0.25, 0.25],
                "flag": 0,
                "edgeColor": [0.0, 0.0, 0.0, 1.0],
                "edgeSize": 1.0,
                "textureIndex": -1,
                "envTextureIndex": -1,
                "envFlag": 0,
                "toonFlag": 1,
                "toonIndex": 0,
                "comment": "",
                "faceCount": 1,
            }
        ],
        "bones": [
            {
                "name": "root",
                "englishName": "root",
                "position": [0.0, 0.0, 0.0],
                "parentIndex": -1,
                "transformationClass": 0,
                "flag": 0,
                "offsetPosition": [0.0, 1.0, 0.0],
            }
        ],
        "morphs": [
            {
                "name": "lift",
                "englishName": "lift",
                "panel": 1,
                "type": 1,
                "elements": [{"index": 2, "position": [0.0, 1.0, 0.0]}],
            }
        ],
        "rigidBodies": [],
        "constraints": [],
    }


def _curve_vmd() -> bytes:
    out = bytearray()
    out += _fixed_text("Vocaloid Motion Data 0002", 30)
    out += _fixed_text("Tiny", 20)
    out += struct.pack("<I", 2)
    for frame, tx, interp in ((0, 0.0, bytes(64)), (30, 10.0, _ease_out_x_interpolation())):
        out += _fixed_text("root", 15)
        out += struct.pack("<I", frame)
        out += struct.pack("<3f", tx, 0.0, 0.0)
        out += struct.pack("<4f", 0.0, 0.0, 0.0, 1.0)
        out += interp
    out += struct.pack("<I", 0)
    out += struct.pack("<I", 0)
    return bytes(out)


def _short_span_vmd() -> bytes:
    out = bytearray()
    out += _fixed_text("Vocaloid Motion Data 0002", 30)
    out += _fixed_text("Tiny", 20)
    out += struct.pack("<I", 2)
    for frame, tx in ((0, 0.0), (1, 10.0)):
        out += _fixed_text("root", 15)
        out += struct.pack("<I", frame)
        out += struct.pack("<3f", tx, 0.0, 0.0)
        out += struct.pack("<4f", 0.0, 0.0, 0.0, 1.0)
        out += bytes(64)
    out += struct.pack("<I", 0)
    out += struct.pack("<I", 0)
    return bytes(out)


def _child_rotation_vmd() -> bytes:
    out = bytearray()
    out += _fixed_text("Vocaloid Motion Data 0002", 30)
    out += _fixed_text("Tiny", 20)
    out += struct.pack("<I", 1)
    out += _fixed_text("child", 15)
    out += struct.pack("<I", 15)
    out += struct.pack("<3f", 0.0, 0.0, 0.0)
    half = np.sqrt(0.5)
    out += struct.pack("<4f", 0.0, 0.0, float(half), float(half))
    out += bytes(64)
    out += struct.pack("<I", 0)
    out += struct.pack("<I", 0)
    return bytes(out)


def _ik_target_vmd() -> bytes:
    out = bytearray()
    out += _fixed_text("Vocaloid Motion Data 0002", 30)
    out += _fixed_text("Tiny", 20)
    out += struct.pack("<I", 1)
    out += _fixed_text("ik", 15)
    out += struct.pack("<I", 10)
    out += struct.pack("<3f", 0.8, -0.5, 0.0)
    out += struct.pack("<4f", 0.0, 0.0, 0.0, 1.0)
    out += bytes(64)
    out += struct.pack("<I", 0)
    out += struct.pack("<I", 0)
    return bytes(out)


def _ease_out_x_interpolation() -> bytes:
    raw = bytearray(64)
    raw[0] = 0
    raw[4] = 127
    raw[8] = 0
    raw[12] = 127
    return bytes(raw)


def test_load_minimal_pmx_and_build_modes(tmp_path: Path) -> None:
    path = tmp_path / "tiny.pmx"
    path.write_bytes(_minimal_pmx())
    model = load_pmx(path)
    assert model.vertex_count == 3
    assert model.triangle_count == 1
    assert len(model.materials) == 1
    assert len(model.bones) == 1
    assert len(model.morphs) == 0
    assert len(model.rigid_bodies) == 1
    assert len(model.joints) == 1
    assert np.allclose(model.bounds_min, (-1.0, 0.0, 0.0))

    toon = build_mmd_render_item(model, render_mode=MMD_RENDER_TOON)
    assert toon["render_mode"] == MMD_RENDER_TOON
    assert toon["lighting"]["preset"] == "studio_soft"
    assert toon["diagnostics"]["draw_group_count"] == 1
    assert toon["groups"][0]["vertex_count"] == 3
    assert toon["diagnostics"]["mmd_vbo_cache_binds"] == 0
    assert toon["diagnostics"]["mmd_vbo_cache_hits"] == 0

    legacy_mode = build_mmd_render_item(model, render_mode="unsupported")
    assert legacy_mode["render_mode"] == MMD_RENDER_TOON

    golden = build_mmd_render_item(model, lighting_preset="golden_hour")
    assert golden["lighting"]["preset"] == "golden_hour"
    assert golden["lighting"]["key_dir"][0] > 0.0
    assert golden["diagnostics"]["lighting_preset"] == "golden_hour"
    assert golden["diagnostics"]["soft_shadow_enabled"] is True
    assert golden["diagnostics"]["shadow_map_size"] == 1024
    assert golden["diagnostics"]["ground_shadow_enabled"] is True
    assert golden["diagnostics"]["bloom_enabled"] is True
    assert golden["diagnostics"]["hemisphere_ambient_enabled"] is True
    assert golden["lighting"]["sky_color"] != golden["lighting"]["ground_color"]
    assert resolve_mmd_lighting("missing")["preset"] == "studio_soft"


def test_load_minimal_pmd_through_shared_loader(tmp_path: Path) -> None:
    path = tmp_path / "tiny.pmd"
    path.write_bytes(_minimal_pmd())
    model = load_pmd(path)
    assert model.name == "TinyPMD"
    assert model.vertex_count == 3
    assert model.triangle_count == 1
    assert len(model.materials) == 1
    assert len(model.bones) == 1
    assert len(model.rigid_bodies) == 1
    assert len(model.joints) == 1

    shared = load_mmd_model(path)
    assert shared.header.version == 1.0
    item = build_mmd_render_item(shared, render_mode=MMD_RENDER_TOON)
    assert item["diagnostics"]["vertex_count"] == 3
    assert item["groups"][0]["edge_enabled"] is True


def test_load_minimal_aplaybox_pbx_json_through_shared_loader(tmp_path: Path) -> None:
    path = tmp_path / "tiny.pbx.json"
    path.write_text(json.dumps(_minimal_pbx_json()), encoding="utf-8")
    model = load_mmd_model(path)
    assert model.name == "TinyPBX"
    assert model.vertex_count == 3
    assert model.triangle_count == 1
    assert len(model.materials) == 1
    assert len(model.bones) == 1
    assert len(model.morphs) == 1
    assert model.morphs[0].vertex_morph is not None

    item = build_mmd_render_item(model, render_mode=MMD_RENDER_TOON)
    assert item["diagnostics"]["vertex_count"] == 3
    assert item["groups"][0]["vertex_count"] == 3
    assert item["groups"][0]["edge_enabled"] is True


def test_load_vmd_camera_and_skin_minimal_pmx(tmp_path: Path) -> None:
    pmx_path = tmp_path / "tiny.pmx"
    pmx_path.write_bytes(_minimal_pmx())
    vmd_path = tmp_path / "tiny.vmd"
    vmd_path.write_bytes(_minimal_vmd())

    model = load_pmx(pmx_path)
    motion = load_vmd(vmd_path)
    assert motion.max_frame == 30
    assert motion.has_model_motion
    assert motion.has_camera_motion
    assert bone_pose_at(motion, 15.0)["root"][0] == (0.0, 1.0, 0.0)
    assert camera_at(motion, 30.0).fov_degrees == 42.0

    pose = evaluate_model_pose(model, motion, 15.0, physics_backend=SpringPhysicsBackend())
    assert pose.skinned
    assert pose.active_bone_count == 1
    assert pose.physics_body_count == 1
    assert np.allclose(pose.positions[:, 1], model.positions[:, 1] + 1.0)

    no_physics_pose = evaluate_model_pose(model, motion, 15.0, physics_backend=NoPhysicsBackend())
    assert no_physics_pose.skinned
    assert no_physics_pose.physics_body_count == 0


def test_gpu_skinning_keeps_vertex_morphs_on_gpu(tmp_path: Path) -> None:
    pmx_path = tmp_path / "tiny.pmx"
    pmx_path.write_bytes(_minimal_pmx())
    vmd_path = tmp_path / "tiny.vmd"
    vmd_path.write_bytes(_minimal_vmd())

    model = load_pmx(pmx_path)
    smile = MMDMorph(
        name="smile",
        english_name="smile",
        panel=1,
        morph_type=1,
        vertex_morph=MMDVertexMorph(
            indices=np.asarray([2], dtype=np.int32),
            offsets=np.asarray([[0.0, 0.25, 0.0]], dtype=np.float32),
        ),
    )
    model = replace(model, morphs=(smile,))
    motion = load_vmd(vmd_path)

    pose = evaluate_model_pose(
        model,
        motion,
        12.0,
        physics_backend=NoPhysicsBackend(),
        skin_vertices=False,
        gpu_morph_slots=2,
    )
    assert pose.skinned is False
    assert pose.active_morph_count == 1
    assert pose.gpu_morph_names == ("smile",)
    assert np.allclose(pose.gpu_morph_weights, (0.75,))
    assert np.allclose(pose.positions, model.positions)

    item = build_mmd_render_item(model, render_mode=MMD_RENDER_TOON, pose_geometry=pose)
    assert item["gpu_skinning"] is True
    assert item["gpu_morph_names"] == ("smile",)
    assert np.allclose(item["gpu_morph_weights"], (0.75,))
    assert item["diagnostics"]["gpu_morph_active_count"] == 1
    assert item["groups"][0]["vertex_stride_floats"] == 22
    rows = np.asarray(item["groups"][0]["vertices"], dtype=np.float32).reshape((-1, 22))
    assert np.allclose(rows[2, 16:19], (0.0, 0.25, 0.0))


def test_vmd_interpolation_curve_affects_bone_translation(tmp_path: Path) -> None:
    path = tmp_path / "curve.vmd"
    path.write_bytes(_curve_vmd())
    motion = load_vmd(path)
    root = bone_pose_at(motion, 15.0)["root"][0]
    assert root[0] > 7.5


def test_vmd_bezier_solver_handles_linear_and_extreme_curves() -> None:
    linear = VMDBezier()
    assert vmd_bezier_is_linear(linear)
    assert abs(vmd_bezier_value(linear, 0.5) - 0.5) < 0.000001

    ease_in = VMDBezier(0.0, 0.0, 1.0, 0.0)
    ease_out = VMDBezier(0.0, 1.0, 1.0, 1.0)
    assert vmd_bezier_value(ease_in, 0.5) < 0.20
    assert vmd_bezier_value(ease_out, 0.5) > 0.80
    assert vmd_bezier_max_linear_delta(ease_in) > 0.25
    assert vmd_bezier_max_linear_delta(ease_out) > 0.25


def test_vmd_fractional_frame_between_adjacent_keys_interpolates(tmp_path: Path) -> None:
    path = tmp_path / "short.vmd"
    path.write_bytes(_short_span_vmd())
    motion = load_vmd(path)
    root = bone_pose_at(motion, 0.5)["root"][0]
    assert 4.9 < root[0] < 5.1


def test_vmd_sampling_cache_returns_independent_dicts(tmp_path: Path) -> None:
    path = tmp_path / "tiny.vmd"
    path.write_bytes(_minimal_vmd())
    motion = load_vmd(path)

    pose = bone_pose_at(motion, 15.0)
    pose["root"] = ((99.0, 99.0, 99.0), (0.0, 0.0, 0.0, 1.0))
    assert bone_pose_at(motion, 15.0)["root"][0] == (0.0, 1.0, 0.0)

    weights = morph_weights_at(motion, 12.0)
    weights["smile"] = 0.0
    assert morph_weights_at(motion, 12.0)["smile"] == 0.75


def test_spring_physics_uses_temporal_state_after_first_frame(tmp_path: Path) -> None:
    pmx_path = tmp_path / "tiny.pmx"
    pmx_path.write_bytes(_minimal_pmx())
    vmd_path = tmp_path / "curve.vmd"
    vmd_path.write_bytes(_curve_vmd())

    model = load_pmx(pmx_path)
    motion = load_vmd(vmd_path)
    backend = SpringPhysicsBackend()
    evaluate_model_pose(model, motion, 0.0, physics_backend=backend)
    physics_pose = evaluate_model_pose(model, motion, 15.0, physics_backend=backend)
    no_physics_pose = evaluate_model_pose(model, motion, 15.0, physics_backend=NoPhysicsBackend())
    assert physics_pose.physics_body_count == 1
    assert float(np.max(np.abs(physics_pose.positions - no_physics_pose.positions))) > 0.0001


def test_spring_physics_offsets_stay_preview_safe(tmp_path: Path) -> None:
    pmx_path = tmp_path / "tiny.pmx"
    pmx_path.write_bytes(_minimal_pmx())
    vmd_path = tmp_path / "curve.vmd"
    vmd_path.write_bytes(_curve_vmd())

    model = load_pmx(pmx_path)
    motion = load_vmd(vmd_path)
    backend = SpringPhysicsBackend()
    peak = 0.0
    for frame in range(0, 46):
        physics_pose = evaluate_model_pose(model, motion, float(frame), physics_backend=backend)
        no_physics_pose = evaluate_model_pose(model, motion, float(frame), physics_backend=NoPhysicsBackend())
        peak = max(peak, float(np.max(np.linalg.norm(physics_pose.positions - no_physics_pose.positions, axis=1))))

    assert peak <= 0.24


def test_spring_physics_response_controls_follow_lag(tmp_path: Path) -> None:
    pmx_path = tmp_path / "tiny.pmx"
    pmx_path.write_bytes(_minimal_pmx())
    model = load_pmx(pmx_path)
    root = replace(model.bones[0], name="root", english_name="root", parent_index=-1, position=(0.0, 0.0, 0.0))
    skirt = replace(
        model.bones[0],
        name="Skirt_0_1",
        english_name="Skirt_0_1",
        parent_index=0,
        position=(0.0, 1.0, 0.0),
    )
    body = MMDRigidBody(
        name="Skirt_0_1",
        english_name="Skirt_0_1",
        bone_index=1,
        collision_group=0,
        collision_mask=0,
        shape=0,
        size=(0.2, 0.4, 0.0),
        position=(0.0, 1.4, 0.0),
        rotation=(0.0, 0.0, 0.0),
        mass=5.0,
        linear_damping=0.05,
        angular_damping=0.05,
        restitution=0.0,
        friction=0.5,
        physics_mode=1,
    )
    model = replace(model, bones=(root, skirt), rigid_bodies=(body,), joints=())
    quick = SpringPhysicsBackend(spring_response=1.20)
    lagged = SpringPhysicsBackend(spring_response=0.35)
    first_globals = [np.eye(4, dtype=np.float32), np.eye(4, dtype=np.float32)]
    first_globals[1][:3, 3] = (0.0, 1.0, 0.0)
    moved_globals = [np.eye(4, dtype=np.float32), np.eye(4, dtype=np.float32)]
    moved_globals[1][:3, 3] = (0.0, 1.0, 0.6)

    quick.offsets_for(model, first_globals, 0.0)
    lagged.offsets_for(model, first_globals, 0.0)
    quick_delta = abs(float(quick.offsets_for(model, moved_globals, 3.0).translation_offsets[1][2]))
    lagged_delta = abs(float(lagged.offsets_for(model, moved_globals, 3.0).translation_offsets[1][2]))

    assert SPRING_PHYSICS_RESPONSE < 1.0
    assert lagged_delta > quick_delta


def test_physics_rotation_offsets_affect_skinning(tmp_path: Path) -> None:
    pmx_path = tmp_path / "tiny.pmx"
    pmx_path.write_bytes(_minimal_pmx())
    vmd_path = tmp_path / "tiny.vmd"
    vmd_path.write_bytes(_minimal_vmd())

    class _Backend:
        def reset(self) -> None:
            return

        def offsets_for(self, _model, _globals, _frame: float):
            half = math.sin(math.radians(35.0) * 0.5)
            return MMDPhysicsPoseDelta({}, 1, {0: (0.0, 0.0, half, math.cos(math.radians(35.0) * 0.5))})

    model = load_pmx(pmx_path)
    motion = load_vmd(vmd_path)
    rotated = evaluate_model_pose(model, motion, 15.0, physics_backend=_Backend())
    baseline = evaluate_model_pose(model, motion, 15.0, physics_backend=NoPhysicsBackend())

    assert rotated.physics_body_count == 1
    assert not np.allclose(rotated.positions, baseline.positions)


def test_spring_physics_generates_secondary_rotation_hints(tmp_path: Path) -> None:
    pmx_path = tmp_path / "tiny.pmx"
    pmx_path.write_bytes(_minimal_pmx())
    model = load_pmx(pmx_path)
    root = replace(model.bones[0], name="root", english_name="root", parent_index=-1, position=(0.0, 0.0, 0.0))
    skirt = replace(
        model.bones[0],
        name="Skirt_0_1",
        english_name="Skirt_0_1",
        parent_index=0,
        position=(0.0, 1.0, 0.0),
    )
    body = MMDRigidBody(
        name="Skirt_0_1",
        english_name="Skirt_0_1",
        bone_index=1,
        collision_group=0,
        collision_mask=0,
        shape=0,
        size=(0.2, 0.4, 0.0),
        position=(0.0, 1.4, 0.0),
        rotation=(0.0, 0.0, 0.0),
        mass=5.0,
        linear_damping=0.05,
        angular_damping=0.05,
        restitution=0.0,
        friction=0.5,
        physics_mode=1,
    )
    model = replace(model, bones=(root, skirt), rigid_bodies=(body,), joints=())
    backend = SpringPhysicsBackend()
    first_globals = [np.eye(4, dtype=np.float32), np.eye(4, dtype=np.float32)]
    first_globals[1][:3, 3] = (0.0, 1.0, 0.0)
    moved_globals = [np.eye(4, dtype=np.float32), np.eye(4, dtype=np.float32)]
    moved_globals[1][:3, 3] = (0.0, 1.0, 0.6)

    first = backend.offsets_for(model, first_globals, 0.0)
    second = backend.offsets_for(model, moved_globals, 3.0)

    assert first.rotation_offsets == {}
    assert second.active_count == 1
    assert 1 in second.rotation_offsets
    assert abs(second.rotation_offsets[1][0]) + abs(second.rotation_offsets[1][1]) + abs(second.rotation_offsets[1][2]) > 0.0001
    huge_hint = SpringPhysicsBackend._rotation_hint_for_body(
        model,
        first_globals,
        1,
        body,
        np.asarray((0.0, 1.4, 0.0), dtype=np.float32),
        np.asarray((0.0, 0.0, 5.0), dtype=np.float32),
    )
    assert huge_hint is not None
    angle = 2.0 * math.atan2(
        math.sqrt(huge_hint[0] * huge_hint[0] + huge_hint[1] * huge_hint[1] + huge_hint[2] * huge_hint[2]),
        abs(huge_hint[3]),
    )
    assert angle <= (0.42 * SECONDARY_ROTATION_HINT_SCALE) + 0.000001

    report = analyze_mmd_model(model, None, sample_frames=[0])
    physics_policy = report["physics_policy"]
    assert physics_policy["secondary_candidate_count"] == 1
    assert physics_policy["probe_active_count"] == 1
    assert physics_policy["probe_translation_bone_count"] == 1
    assert physics_policy["probe_rotation_bone_count"] == 1
    assert physics_policy["probe_max_rotation_degrees"] > 0.05
    assert "physics_secondary_rotation" in report["feature_flags"]
    assert "mmd_physics_secondary_rotation_missing" not in report["risk_codes"]


def test_mmd_physics_backend_factory_falls_back_without_pybullet(monkeypatch) -> None:
    monkeypatch.delenv("TIGERCAPTURE_MMD_PHYSICS_BACKEND", raising=False)
    auto_backend = create_mmd_physics_backend("auto")
    assert isinstance(auto_backend, (SpringPhysicsBackend, PyBulletPhysicsBackend))

    bullet_backend = create_mmd_physics_backend("pybullet")
    assert hasattr(bullet_backend, "offsets_for")
    assert isinstance(create_mmd_physics_backend("none"), NoPhysicsBackend)


def test_mmd_physics_backend_diagnostics_reports_fallback() -> None:
    backend = DecimatedPhysicsBackend(create_mmd_physics_backend("pybullet"))
    diagnostics = mmd_physics_backend_diagnostics(backend)
    assert diagnostics["physics_decimated_backend"] is True
    assert diagnostics["physics_backend_requested"] == "pybullet"
    assert diagnostics["physics_backend"] in {"pybullet", "spring"}
    assert isinstance(diagnostics["physics_backend_fallback"], bool)
    assert isinstance(diagnostics["physics_backend_joint_frame_constraint_count"], int)
    assert isinstance(diagnostics["physics_backend_joint_limit_correction_count"], int)
    assert isinstance(diagnostics["physics_backend_joint_spring_correction_count"], int)
    assert isinstance(diagnostics["physics_backend_orientation_feedback_count"], int)
    assert isinstance(diagnostics["physics_backend_solver_iterations"], int)
    assert isinstance(diagnostics["physics_backend_solver_substeps"], int)
    assert isinstance(diagnostics["physics_backend_constraint_force_avg"], float)
    assert isinstance(diagnostics["physics_backend_shape_capsule_count"], int)
    assert isinstance(diagnostics["physics_backend_capsule_axis_fix_count"], int)


def test_pybullet_solver_tuning_scales_with_model_complexity() -> None:
    assert PyBulletPhysicsBackend._solver_iterations_for(0, 0) == 24
    assert PyBulletPhysicsBackend._solver_iterations_for(120, 160) == 36
    assert PyBulletPhysicsBackend._solver_iterations_for(300, 420) == 48
    assert PyBulletPhysicsBackend._solver_iterations_for(381, 574) == 56


def test_pybullet_configure_solver_records_parameters() -> None:
    class FakePyBullet:
        def __init__(self) -> None:
            self.time_steps = []
            self.params = []

        def setTimeStep(self, value: float, physicsClientId: int | None = None) -> None:
            self.time_steps.append((value, physicsClientId))

        def setPhysicsEngineParameter(self, **kwargs) -> None:
            self.params.append(kwargs)

    backend = PyBulletPhysicsBackend()
    backend.client_id = 1
    fake_pb = FakePyBullet()
    backend._configure_solver(fake_pb, active_body_count=381, joint_count=574)

    assert backend.last_solver_iterations == 56
    assert backend.last_solver_active_body_count == 381
    assert backend.last_solver_joint_count == 574
    assert backend.last_solver_fixed_time_step == pytest.approx(1.0 / 120.0)
    assert fake_pb.time_steps[-1][0] == pytest.approx(1.0 / 120.0)
    assert fake_pb.params[-1]["numSolverIterations"] == 56
    assert fake_pb.params[-1]["deterministicOverlappingPairs"] == 1


def test_pybullet_joint_limit_helpers_sort_pmx_bounds() -> None:
    joint = MMDJoint(
        name="joint",
        english_name="",
        joint_type=0,
        rigid_body_a=0,
        rigid_body_b=1,
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0),
        linear_lower=(0.2, -0.1, 0.4),
        linear_upper=(-0.2, 0.3, -0.4),
        angular_lower=(0.5, -0.3, 0.1),
        angular_upper=(-0.5, 0.2, -0.2),
        linear_spring=(0.0, 0.0, 0.0),
        angular_spring=(0.0, 0.0, 0.0),
    )
    linear_lower, linear_upper = PyBulletPhysicsBackend._joint_linear_bounds(joint)
    angular_lower, angular_upper = PyBulletPhysicsBackend._joint_angular_bounds(joint)
    assert np.allclose(linear_lower, (-0.2, -0.1, -0.4))
    assert np.allclose(linear_upper, (0.2, 0.3, 0.4))
    assert np.allclose(angular_lower, (-0.5, -0.3, -0.2))
    assert np.allclose(angular_upper, (0.5, 0.2, 0.1))


def test_pybullet_joint_constraint_force_uses_spring_and_mass() -> None:
    joint_soft = MMDJoint(
        name="soft",
        english_name="",
        joint_type=0,
        rigid_body_a=0,
        rigid_body_b=1,
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0),
        linear_lower=(0.0, 0.0, 0.0),
        linear_upper=(0.0, 0.0, 0.0),
        angular_lower=(0.0, 0.0, 0.0),
        angular_upper=(0.0, 0.0, 0.0),
        linear_spring=(0.0, 0.0, 0.0),
        angular_spring=(0.0, 0.0, 0.0),
    )
    joint_stiff = replace(
        joint_soft,
        linear_spring=(1200.0, 0.0, 0.0),
        angular_spring=(400.0, 0.0, 0.0),
    )
    body_a = MMDRigidBody(
        name="a",
        english_name="",
        bone_index=0,
        collision_group=0,
        collision_mask=0,
        shape=0,
        size=(0.1, 0.1, 0.1),
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0),
        mass=2.0,
        linear_damping=0.0,
        angular_damping=0.0,
        restitution=0.0,
        friction=0.5,
        physics_mode=1,
    )
    body_b = replace(body_a, name="b", mass=4.0)
    backend = PyBulletPhysicsBackend()

    soft_force = backend._joint_constraint_max_force(joint_soft, body_a, body_b)
    stiff_force = backend._joint_constraint_max_force(joint_stiff, body_a, body_b)
    assert soft_force > 18.0
    assert stiff_force > soft_force
    assert stiff_force <= 260.0


def test_pybullet_capsule_collision_shape_is_rotated_to_mmd_y_axis() -> None:
    class FakePyBullet:
        GEOM_BOX = 1
        GEOM_CAPSULE = 2
        GEOM_SPHERE = 3

        def __init__(self) -> None:
            self.calls = []

        def createCollisionShape(self, *args, **kwargs):
            self.calls.append((args, kwargs))
            return 77

    body = MMDRigidBody(
        name="capsule",
        english_name="",
        bone_index=0,
        collision_group=0,
        collision_mask=0,
        shape=2,
        size=(0.2, 1.0, 0.0),
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0),
        mass=1.0,
        linear_damping=0.0,
        angular_damping=0.0,
        restitution=0.0,
        friction=0.5,
        physics_mode=1,
    )
    backend = PyBulletPhysicsBackend()
    backend.client_id = 1
    fake_pb = FakePyBullet()
    shape_id = backend._create_collision_shape(fake_pb, 0, body)

    assert shape_id == 77
    assert backend.shape_type_counts["capsule"] == 1
    assert backend.last_capsule_axis_fix_count == 1
    args, kwargs = fake_pb.calls[0]
    assert args[0] == fake_pb.GEOM_CAPSULE
    assert kwargs["radius"] == pytest.approx(0.2)
    assert kwargs["height"] == pytest.approx(2.0)
    q = kwargs["collisionFrameOrientation"]
    assert q[0] == pytest.approx(-math.sin(math.pi * 0.25))
    assert q[3] == pytest.approx(math.cos(math.pi * 0.25))


def test_pybullet_joint_constraint_uses_body_local_pivots() -> None:
    class FakePyBullet:
        JOINT_POINT2POINT = 5

        def __init__(self) -> None:
            self.created = None

        def createConstraint(self, *args, **kwargs):
            self.created = (args, kwargs)
            return 42

        def changeConstraint(self, *_args, **_kwargs) -> None:
            return

    backend = PyBulletPhysicsBackend()
    backend.client_id = 1
    backend.body_ids = {0: 10, 1: 11}
    body = object()
    half_turn_z = (0.0, 0.0, math.sin(math.pi * 0.25), math.cos(math.pi * 0.25))
    identity = (0.0, 0.0, 0.0, 1.0)
    entries = {
        0: (0, body, np.asarray((0.0, 0.0, 0.0), dtype=np.float32), half_turn_z, True),
        1: (1, body, np.asarray((0.0, 0.0, 0.0), dtype=np.float32), identity, True),
    }
    joint = MMDJoint(
        name="joint",
        english_name="",
        joint_type=0,
        rigid_body_a=0,
        rigid_body_b=1,
        position=(1.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0),
        linear_lower=(0.0, 0.0, 0.0),
        linear_upper=(0.0, 0.0, 0.0),
        angular_lower=(0.0, 0.0, 0.0),
        angular_upper=(0.0, 0.0, 0.0),
        linear_spring=(0.0, 0.0, 0.0),
        angular_spring=(0.0, 0.0, 0.0),
    )
    fake_pb = FakePyBullet()
    backend._ensure_joint_constraint(fake_pb, 0, joint, entries)

    assert fake_pb.created is not None
    args, _kwargs = fake_pb.created
    assert np.allclose(args[6], (0.0, -1.0, 0.0), atol=0.00001)
    assert np.allclose(args[7], (1.0, 0.0, 0.0), atol=0.00001)


def test_pybullet_joint_limit_correction_moves_bodies_toward_bounds() -> None:
    class FakePyBullet:
        def __init__(self) -> None:
            self.states = {
                10: ([0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0]),
                11: ([1.5, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0]),
            }

        def getBasePositionAndOrientation(self, body_id: int, physicsClientId: int | None = None):
            return self.states[body_id]

        def resetBasePositionAndOrientation(self, body_id: int, pos, orn, physicsClientId: int | None = None) -> None:
            self.states[body_id] = (list(pos), list(orn))

        def getEulerFromQuaternion(self, _quat):
            return (0.0, 0.0, 0.0)

    backend = PyBulletPhysicsBackend()
    backend.client_id = 1
    backend.body_ids = {0: 10, 1: 11}
    body = object()
    identity = (0.0, 0.0, 0.0, 1.0)
    entries = {
        0: (0, body, np.asarray((0.0, 0.0, 0.0), dtype=np.float32), identity, True),
        1: (1, body, np.asarray((1.0, 0.0, 0.0), dtype=np.float32), identity, True),
    }
    joint = MMDJoint(
        name="joint",
        english_name="",
        joint_type=0,
        rigid_body_a=0,
        rigid_body_b=1,
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0),
        linear_lower=(0.0, 0.0, 0.0),
        linear_upper=(0.0, 0.0, 0.0),
        angular_lower=(-1.0, -1.0, -1.0),
        angular_upper=(1.0, 1.0, 1.0),
        linear_spring=(0.0, 0.0, 0.0),
        angular_spring=(0.0, 0.0, 0.0),
    )
    fake_pb = FakePyBullet()
    backend._apply_joint_limit_corrections(fake_pb, [joint], entries, 1.0 / 60.0)

    assert backend.last_joint_limit_correction_count == 1
    assert fake_pb.states[10][0][0] > 0.0
    assert fake_pb.states[11][0][0] < 1.5


def test_pybullet_joint_limit_correction_uses_joint_local_axes() -> None:
    class FakePyBullet:
        def __init__(self) -> None:
            self.states = {
                10: ([0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0]),
                11: ([0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]),
            }

        def getBasePositionAndOrientation(self, body_id: int, physicsClientId: int | None = None):
            return self.states[body_id]

        def resetBasePositionAndOrientation(self, body_id: int, pos, orn, physicsClientId: int | None = None) -> None:
            self.states[body_id] = (list(pos), list(orn))

        def getEulerFromQuaternion(self, _quat):
            return (0.0, 0.0, 0.0)

    backend = PyBulletPhysicsBackend()
    backend.client_id = 1
    backend.body_ids = {0: 10, 1: 11}
    body = object()
    identity = (0.0, 0.0, 0.0, 1.0)
    entries = {
        0: (0, body, np.asarray((0.0, 0.0, 0.0), dtype=np.float32), identity, True),
        1: (1, body, np.asarray((0.0, 0.0, 0.0), dtype=np.float32), identity, True),
    }
    joint = MMDJoint(
        name="joint",
        english_name="",
        joint_type=0,
        rigid_body_a=0,
        rigid_body_b=1,
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, math.pi * 0.5),
        linear_lower=(-2.0, -0.05, -0.05),
        linear_upper=(2.0, 0.05, 0.05),
        angular_lower=(-1.0, -1.0, -1.0),
        angular_upper=(1.0, 1.0, 1.0),
        linear_spring=(0.0, 0.0, 0.0),
        angular_spring=(0.0, 0.0, 0.0),
    )
    fake_pb = FakePyBullet()
    backend._apply_joint_limit_corrections(fake_pb, [joint], entries, 1.0 / 60.0)

    assert backend.last_joint_limit_correction_count == 0
    assert fake_pb.states[11][0] == [0.0, 1.0, 0.0]


def test_pybullet_collision_group_mask_uses_pmx_no_collision_mask() -> None:
    body = MMDRigidBody(
        name="rb",
        english_name="",
        bone_index=0,
        collision_group=2,
        collision_mask=0b0000000000001010,
        shape=0,
        size=(0.1, 0.1, 0.1),
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0),
        mass=1.0,
        linear_damping=0.0,
        angular_damping=0.0,
        restitution=0.0,
        friction=0.5,
        physics_mode=1,
    )
    group, mask = PyBulletPhysicsBackend._collision_group_mask(body)
    assert group == 0b100
    assert mask & 0b1010 == 0
    assert mask & 0b0100


def test_mmd_physics_backend_factory_applies_tuning() -> None:
    backend = create_mmd_physics_backend("spring", spring_response=0.50, secondary_rotation_scale=0.20)
    assert isinstance(backend, SpringPhysicsBackend)
    assert backend.spring_response == 0.50
    assert backend.secondary_rotation_scale == 0.20

    wrapped = DecimatedPhysicsBackend(backend)
    configure_mmd_physics_backend(wrapped, spring_response=0.80, secondary_rotation_scale=0.10)
    assert backend.spring_response == 0.80
    assert backend.secondary_rotation_scale == 0.10


def test_transparent_material_enters_mmd_render_queue(tmp_path: Path) -> None:
    path = tmp_path / "tiny.pmx"
    path.write_bytes(_minimal_pmx())
    model = load_pmx(path)
    material = replace(model.materials[0], diffuse=(0.8, 0.7, 0.6, 0.5))
    model = replace(model, materials=(material,))

    item = build_mmd_render_item(model, render_mode=MMD_RENDER_TOON)
    group = item["groups"][0]
    assert group["render_bucket"] == MMD_RENDER_BUCKET_TRANSPARENT
    assert group["depth_write"] is False
    assert item["diagnostics"]["transparent_group_count"] == 1


def test_transparent_materials_sort_by_depth_range(tmp_path: Path) -> None:
    path = tmp_path / "tiny.pmx"
    path.write_bytes(_minimal_pmx())
    model = load_pmx(path)
    positions = np.asarray(
        [
            (-1.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (-1.0, 0.0, 1.0),
            (1.0, 0.0, 1.0),
            (0.0, 1.0, 1.0),
        ],
        dtype=np.float32,
    )
    normals = np.asarray([(0.0, 0.0, 1.0)] * 6, dtype=np.float32)
    uvs = np.asarray([(0.0, 0.0), (1.0, 0.0), (0.5, 1.0)] * 2, dtype=np.float32)
    indices = np.asarray([0, 1, 2, 3, 4, 5], dtype=np.int32)
    near = replace(model.materials[0], diffuse=(0.8, 0.7, 0.6, 0.5), surface_count=3)
    far = replace(model.materials[0], diffuse=(0.6, 0.7, 0.8, 0.5), surface_count=3)
    model = replace(
        model,
        positions=positions,
        normals=normals,
        uvs=uvs,
        indices=indices,
        materials=(near, far),
        bounds_min=(-1.0, 0.0, 0.0),
        bounds_max=(1.0, 1.0, 1.0),
    )

    item = build_mmd_render_item(model, render_mode=MMD_RENDER_TOON, yaw=0.0, pitch=0.0)
    assert [group["material_index"] for group in item["groups"]] == [1, 0]
    assert item["diagnostics"]["transparent_sort_depth_monotonic"] is True


def test_cutout_alpha_texture_keeps_depth_write(tmp_path: Path) -> None:
    from PIL import Image

    path = tmp_path / "tiny.pmx"
    path.write_bytes(_minimal_pmx())
    texture_path = tmp_path / "mask.png"
    image = Image.new("RGBA", (2, 1))
    image.putdata([(255, 255, 255, 0), (255, 255, 255, 255)])
    image.save(texture_path)

    model = load_pmx(path)
    material = replace(model.materials[0], texture_index=0)
    model = replace(model, textures=("mask.png",), materials=(material,))

    item = build_mmd_render_item(model, render_mode=MMD_RENDER_TOON)
    group = item["groups"][0]
    assert group["render_bucket"] == MMD_RENDER_BUCKET_CUTOUT
    assert group["depth_write"] is True
    assert group["alpha_cutoff"] >= 0.25


def test_near_opaque_hair_alpha_texture_keeps_depth_write(tmp_path: Path) -> None:
    from PIL import Image

    path = tmp_path / "tiny.pmx"
    path.write_bytes(_minimal_pmx())
    texture_path = tmp_path / "hair_soft_alpha.png"
    image = Image.new("RGBA", (20, 1), (255, 255, 255, 255))
    pixels = [(255, 255, 255, 255)] * 19 + [(255, 255, 255, 168)]
    image.putdata(pixels)
    image.save(texture_path)

    model = load_pmx(path)
    material = replace(model.materials[0], name="front hair", texture_index=0)
    model = replace(model, textures=("hair_soft_alpha.png",), materials=(material,))

    item = build_mmd_render_item(model, render_mode=MMD_RENDER_TOON)
    group = item["groups"][0]
    assert group["material_class"] == MMD_MATERIAL_HAIR
    assert group["render_bucket"] == MMD_RENDER_BUCKET_OPAQUE
    assert group["depth_write"] is True
    assert item["diagnostics"]["transparent_group_count"] == 0


def test_material_uv_alpha_gradient_promotes_front_hair_to_transparent(tmp_path: Path) -> None:
    from PIL import Image

    path = tmp_path / "tiny.pmx"
    path.write_bytes(_minimal_pmx())
    texture_path = tmp_path / "hair_local_gradient.png"
    image = Image.new("RGBA", (32, 32), (255, 255, 255, 255))
    pixels = image.load()
    for y in range(32):
        pixels[0, y] = (255, 255, 255, 160)
    image.save(texture_path)

    model = load_pmx(path)
    material = replace(model.materials[0], name="front hair", texture_index=0)
    uvs = np.asarray([(0.0, 0.1), (0.0, 0.5), (0.0, 0.9)], dtype=np.float32)
    model = replace(model, textures=("hair_local_gradient.png",), materials=(material,), uvs=uvs)

    item = build_mmd_render_item(model, render_mode=MMD_RENDER_TOON)
    group = item["groups"][0]
    assert group["material_class"] == MMD_MATERIAL_HAIR
    assert group["uv_alpha_mode"] == "blend"
    assert group["uv_alpha_mid_ratio"] >= 0.9
    assert group["render_bucket"] == MMD_RENDER_BUCKET_TRANSPARENT
    assert group["depth_write"] is False
    assert item["diagnostics"]["transparent_group_count"] == 1


def test_toon_shadow_color_uses_darkest_ramp_pixel(tmp_path: Path) -> None:
    from PIL import Image

    path = tmp_path / "tiny.pmx"
    path.write_bytes(_minimal_pmx())
    toon_path = tmp_path / "toon_ramp.png"
    image = Image.new("RGBA", (3, 1))
    image.putdata([
        (210, 220, 255, 255),
        (18, 28, 74, 255),
        (128, 140, 210, 255),
    ])
    image.save(toon_path)

    model = load_pmx(path)
    material = replace(model.materials[0], toon_texture_index=0, toon_shared=False)
    model = replace(model, textures=("toon_ramp.png",), materials=(material,))

    item = build_mmd_render_item(model, render_mode=MMD_RENDER_TOON)
    assert np.allclose(item["groups"][0]["toon_shadow_color"], (18 / 255.0, 28 / 255.0, 74 / 255.0))


def test_material_bucket_diagnostics_expose_named_draw_order(tmp_path: Path) -> None:
    path = tmp_path / "tiny.pmx"
    path.write_bytes(_minimal_pmx())
    model = load_pmx(path)
    positions = np.asarray(
        [
            (-1.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (-0.8, 0.1, 0.0),
            (0.8, 0.1, 0.0),
            (0.0, 0.9, 0.0),
        ],
        dtype=np.float32,
    )
    normals = np.asarray([(0.0, 0.0, 1.0)] * 6, dtype=np.float32)
    uvs = np.asarray([(0.0, 0.0), (1.0, 0.0), (0.5, 1.0)] * 2, dtype=np.float32)
    indices = np.asarray([0, 1, 2, 3, 4, 5], dtype=np.int32)
    skin = replace(model.materials[0], name="skin face", surface_count=3)
    eye = replace(model.materials[0], name="eye highlight", diffuse=(0.8, 0.9, 1.0, 0.5), surface_count=3)
    model = replace(
        model,
        positions=positions,
        normals=normals,
        uvs=uvs,
        indices=indices,
        materials=(skin, eye),
        bounds_min=(-1.0, 0.0, 0.0),
        bounds_max=(1.0, 1.0, 0.0),
    )

    item = build_mmd_render_item(model, render_mode=MMD_RENDER_TOON, yaw=0.0, pitch=0.0)
    rows = item["diagnostics"]["material_bucket_rows"]

    assert [row["material_class_name"] for row in rows] == ["skin", "eye"]
    assert [row["render_bucket_name"] for row in rows] == ["opaque", "transparent"]
    assert item["diagnostics"]["material_bucket_counts"] == {"opaque": 1, "cutout": 0, "transparent": 1}
    assert item["diagnostics"]["material_class_counts"]["skin"] == 1
    assert item["diagnostics"]["material_class_counts"]["eye"] == 1
    assert item["diagnostics"]["transparent_material_rows"][0]["material_class_name"] == "eye"
    assert item["groups"][0]["draw_sort_key"] < item["groups"][1]["draw_sort_key"]


def test_material_classes_drive_toon_safe_shader_controls(tmp_path: Path) -> None:
    path = tmp_path / "tiny.pmx"
    path.write_bytes(_minimal_pmx())
    model = load_pmx(path)

    skin = replace(model.materials[0], name="\u808c", english_name="skin face")
    skin_item = build_mmd_render_item(replace(model, materials=(skin,)), render_mode=MMD_RENDER_TOON)
    skin_group = skin_item["groups"][0]
    assert skin_group["material_class"] == MMD_MATERIAL_SKIN
    assert skin_group["skin_warmth"] > 0.0
    assert skin_group["highlight_clamp"] < 1.0
    assert skin_group["toon_ao_strength"] < 0.05
    assert skin_group["skin_shadow_soften"] > 0.0
    assert skin_group["skin_shadow_lift"] > 0.0
    assert skin_group["wrap_diffuse"] > 0.20
    assert skin_item["diagnostics"]["skin_group_count"] == 1

    chinese_face = replace(model.materials[0], name="\u989c")
    chinese_face_item = build_mmd_render_item(replace(model, materials=(chinese_face,)), render_mode=MMD_RENDER_TOON)
    assert chinese_face_item["groups"][0]["material_class"] == MMD_MATERIAL_SKIN

    outlined_face = replace(
        model.materials[0],
        name="\u989c",
        flags=0x10,
        edge_color=(0.0, 0.0, 0.0, 1.0),
        edge_size=1.0,
    )
    outlined_face_item = build_mmd_render_item(replace(model, materials=(outlined_face,)), render_mode=MMD_RENDER_TOON)
    outlined_face_group = outlined_face_item["groups"][0]
    assert outlined_face_group["material_class"] == MMD_MATERIAL_SKIN
    assert outlined_face_group["edge_enabled"] is True
    assert outlined_face_group["edge_size"] < 0.30
    assert max(outlined_face_group["edge_color"][:3]) > 0.10

    hair = replace(model.materials[0], name="\u9aea", english_name="hair")
    hair_item = build_mmd_render_item(replace(model, materials=(hair,)), render_mode=MMD_RENDER_TOON)
    hair_group = hair_item["groups"][0]
    assert hair_group["material_class"] == MMD_MATERIAL_HAIR
    assert hair_group["rim_boost"] > 1.0
    assert hair_group["sphere_strength"] < 1.0
    assert hair_group["toon_highlight_strength"] > 0.0
    assert hair_group["hair_angel_ring_strength"] == 0.0
    assert "hair_ring_bounds_min" not in hair_group
    assert "hair_ring_bounds_max" not in hair_group
    assert hair_item["diagnostics"]["hair_group_count"] == 1

    outlined_hair = replace(
        model.materials[0],
        name="\u9aea",
        english_name="hair",
        diffuse=(0.82, 0.72, 0.48, 1.0),
        flags=0x10,
        edge_color=(0.0, 0.0, 0.0, 1.0),
        edge_size=1.0,
    )
    outlined_hair_item = build_mmd_render_item(replace(model, materials=(outlined_hair,)), render_mode=MMD_RENDER_TOON)
    outlined_hair_group = outlined_hair_item["groups"][0]
    assert outlined_hair_group["material_class"] == MMD_MATERIAL_HAIR
    assert outlined_hair_group["edge_enabled"] is True
    assert outlined_hair_group["edge_size"] < 0.25
    assert max(outlined_hair_group["edge_color"][:3]) > 0.10
    assert outlined_hair_group["edge_color"][3] <= 0.40
    assert np.allclose(outlined_hair_group["edge_color"][:3], (0.722, 0.634, 0.422), atol=0.002)

    internal_hair = replace(
        model.materials[0],
        name="\u524d\u9aea",
        english_name="front hair",
        flags=0x10,
        edge_color=(0.0, 0.0, 0.0, 1.0),
        edge_size=1.0,
    )
    internal_hair_item = build_mmd_render_item(replace(model, materials=(internal_hair,)), render_mode=MMD_RENDER_TOON)
    internal_hair_group = internal_hair_item["groups"][0]
    assert internal_hair_group["material_class"] == MMD_MATERIAL_HAIR
    assert internal_hair_group["edge_enabled"] is False

    from PIL import Image

    bright_hair_texture = tmp_path / "bright_hair.png"
    Image.new("RGBA", (2, 2), (220, 195, 155, 255)).save(bright_hair_texture)
    bright_head_hair = replace(
        model.materials[0],
        name="\u9aee",
        english_name="",
        texture_index=0,
        flags=0x10,
        edge_color=(0.0, 0.0, 0.0, 1.0),
        edge_size=1.0,
    )
    bright_head_hair_item = build_mmd_render_item(
        replace(model, textures=("bright_hair.png",), materials=(bright_head_hair,)),
        render_mode=MMD_RENDER_TOON,
    )
    bright_head_hair_group = bright_head_hair_item["groups"][0]
    assert bright_head_hair_group["material_class"] == MMD_MATERIAL_HAIR
    assert bright_head_hair_group["edge_enabled"] is False

    hair_accessory = replace(model.materials[0], name="\u9aea\u5e26", english_name="hairband")
    hair_accessory_item = build_mmd_render_item(replace(model, materials=(hair_accessory,)), render_mode=MMD_RENDER_TOON)
    assert hair_accessory_item["groups"][0]["material_class"] == MMD_MATERIAL_DEFAULT
    assert hair_accessory_item["groups"][0]["hair_angel_ring_strength"] == 0.0

    hair_textured_head_ornament = replace(
        model.materials[0],
        name="\u5934\u9970",
        texture_index=0,
        flags=0x10,
        edge_color=(0.0, 0.0, 0.0, 1.0),
        edge_size=1.0,
    )
    hair_textured_head_ornament_item = build_mmd_render_item(
        replace(model, textures=("\u9aea.png",), materials=(hair_textured_head_ornament,)),
        render_mode=MMD_RENDER_TOON,
    )
    hair_textured_head_ornament_group = hair_textured_head_ornament_item["groups"][0]
    assert hair_textured_head_ornament_group["material_class"] == MMD_MATERIAL_METAL
    assert hair_textured_head_ornament_group["edge_enabled"] is False

    eye = replace(model.materials[0], name="\u76ee\u5149", english_name="eye highlight")
    eye_item = build_mmd_render_item(replace(model, materials=(eye,)), render_mode=MMD_RENDER_TOON)
    eye_group = eye_item["groups"][0]
    assert eye_group["material_class"] == MMD_MATERIAL_EYE
    assert eye_group["eye_highlight_strength"] > 0.0
    assert eye_group["emissive_strength"] > 0.0
    assert eye_group["diffuse"][3] <= 0.24
    assert eye_group["edge_enabled"] is False
    assert eye_item["diagnostics"]["eye_group_count"] == 1
    assert eye_item["diagnostics"]["bloom_group_count"] == 1

    eye_shadow = replace(model.materials[0], name="\u76ee\u5f71", diffuse=(1.0, 1.0, 1.0, 0.45))
    eye_shadow_item = build_mmd_render_item(replace(model, materials=(eye_shadow,)), render_mode=MMD_RENDER_TOON)
    eye_shadow_group = eye_shadow_item["groups"][0]
    assert eye_shadow_group["material_class"] == MMD_MATERIAL_TRANSPARENT
    assert eye_shadow_group["diffuse"][3] <= 0.22
    assert eye_shadow_group["face_layer_priority"] == 30
    assert eye_shadow_group["edge_enabled"] is False

    lip = replace(model.materials[0], name="\u53e3\u820c", english_name="mouth tongue")
    lip_item = build_mmd_render_item(replace(model, materials=(lip,)), render_mode=MMD_RENDER_TOON)
    lip_group = lip_item["groups"][0]
    assert lip_group["material_class"] == MMD_MATERIAL_LIP
    assert lip_group["lip_specular_strength"] > 0.0
    assert lip_group["edge_enabled"] is False
    assert lip_item["diagnostics"]["lip_group_count"] == 1

    brow_lash = replace(model.materials[0], name="\u776b\u7709", english_name="eyelash brow")
    brow_lash_item = build_mmd_render_item(replace(model, materials=(brow_lash,)), render_mode=MMD_RENDER_TOON)
    brow_lash_group = brow_lash_item["groups"][0]
    assert brow_lash_group["material_class"] == MMD_MATERIAL_DEFAULT
    assert brow_lash_group["edge_enabled"] is False

    mouth_line = replace(model.materials[0], name="\u53e3\u7ebf", english_name="mouthline")
    mouth_line_item = build_mmd_render_item(replace(model, materials=(mouth_line,)), render_mode=MMD_RENDER_TOON)
    mouth_line_group = mouth_line_item["groups"][0]
    assert mouth_line_group["material_class"] == MMD_MATERIAL_LIP
    assert mouth_line_group["edge_enabled"] is False

    korean_mouth = replace(model.materials[0], name="\uc785\uc220", english_name="")
    korean_mouth_item = build_mmd_render_item(replace(model, materials=(korean_mouth,)), render_mode=MMD_RENDER_TOON)
    korean_mouth_group = korean_mouth_item["groups"][0]
    assert korean_mouth_group["material_class"] == MMD_MATERIAL_LIP
    assert korean_mouth_group["edge_enabled"] is False

    metal = replace(model.materials[0], name="\u91d1\u5c5e", english_name="metal jewel", sphere_texture_index=0, sphere_mode=2)
    metal_item = build_mmd_render_item(
        replace(model, textures=("metal_sphere.spa",), materials=(metal,)),
        render_mode=MMD_RENDER_TOON,
    )
    metal_group = metal_item["groups"][0]
    assert metal_group["material_class"] == MMD_MATERIAL_METAL
    assert metal_group["matcap_specular_strength"] > 0.0
    assert metal_group["sphere_strength"] > 1.0
    assert metal_item["diagnostics"]["metal_group_count"] == 1

    skin_named_with_hair_texture = replace(model.materials[0], name="\u808c+", texture_index=0)
    skin_named_item = build_mmd_render_item(
        replace(model, textures=("\u9aea.png",), materials=(skin_named_with_hair_texture,)),
        render_mode=MMD_RENDER_TOON,
    )
    assert skin_named_item["groups"][0]["material_class"] == MMD_MATERIAL_SKIN

    sleeve_named_with_hair_texture = replace(model.materials[0], name="\u8863\u8896", texture_index=0)
    sleeve_named_item = build_mmd_render_item(
        replace(model, textures=("\u9aea.png",), materials=(sleeve_named_with_hair_texture,)),
        render_mode=MMD_RENDER_TOON,
    )
    assert sleeve_named_item["groups"][0]["material_class"] == MMD_MATERIAL_DEFAULT

    shoe_named_with_body_texture = replace(model.materials[0], name="\u978b", texture_index=0)
    shoe_named_item = build_mmd_render_item(
        replace(model, textures=("\u4f53.png",), materials=(shoe_named_with_body_texture,)),
        render_mode=MMD_RENDER_TOON,
    )
    assert shoe_named_item["groups"][0]["material_class"] == MMD_MATERIAL_DEFAULT

    stocking = replace(model.materials[0], name="\u817f", texture_index=0, sphere_texture_index=1, sphere_mode=2)
    stocking_item = build_mmd_render_item(
        replace(model, textures=("\u9ed1\u4e1d.png", "stocking_sphere.spa"), materials=(stocking,)),
        render_mode=MMD_RENDER_TOON,
    )
    stocking_group = stocking_item["groups"][0]
    assert stocking_group["material_class"] == MMD_MATERIAL_STOCKING
    assert stocking_group["sphere_strength"] > 1.0
    assert stocking_group["matcap_specular_strength"] > 0.0
    assert stocking_item["diagnostics"]["stocking_group_count"] == 1

    transparent = replace(model.materials[0], name="glass", diffuse=(0.8, 0.7, 0.6, 0.5))
    transparent_item = build_mmd_render_item(replace(model, materials=(transparent,)), render_mode=MMD_RENDER_TOON)
    transparent_group = transparent_item["groups"][0]
    assert transparent_group["material_class"] == MMD_MATERIAL_TRANSPARENT
    assert transparent_group["toon_ao_strength"] == 0.0

    emissive = replace(model.materials[0], name="AutoLuminous", english_name="neon light")
    emissive_item = build_mmd_render_item(replace(model, materials=(emissive,)), render_mode=MMD_RENDER_TOON)
    emissive_group = emissive_item["groups"][0]
    assert emissive_group["material_class"] == MMD_MATERIAL_EMISSIVE
    assert emissive_group["emissive_strength"] > 0.0
    assert emissive_item["diagnostics"]["bloom_group_count"] == 1

    screen = replace(model.materials[0], name="\u5c4f\u5e55", english_name="")
    screen_item = build_mmd_render_item(replace(model, materials=(screen,)), render_mode=MMD_RENDER_TOON)
    screen_group = screen_item["groups"][0]
    assert screen_group["material_class"] == MMD_MATERIAL_EMISSIVE
    assert screen_group["emissive_strength"] > 0.0
    assert screen_item["diagnostics"]["bloom_group_count"] == 1


def test_material_self_shadow_policy_respects_pmx_flags_and_face_details(tmp_path: Path) -> None:
    path = tmp_path / "tiny.pmx"
    path.write_bytes(_minimal_pmx())
    model = load_pmx(path)

    shadowed_skin = replace(model.materials[0], name="skin face", flags=0x1F)
    shadowed_item = build_mmd_render_item(replace(model, materials=(shadowed_skin,)), render_mode=MMD_RENDER_TOON)
    shadowed_group = shadowed_item["groups"][0]
    assert shadowed_group["casts_self_shadow"] is True
    assert shadowed_group["receives_self_shadow"] is True
    assert shadowed_group["shadow_policy"] == "pmx_flags"
    assert shadowed_group["pmx_cast_self_shadow"] is True
    assert shadowed_group["pmx_receive_self_shadow"] is True
    assert shadowed_item["diagnostics"]["self_shadow_caster_group_count"] == 1
    assert shadowed_item["diagnostics"]["self_shadow_receiver_group_count"] == 1

    ground_only_skin = replace(model.materials[0], name="skin face", flags=0x03)
    ground_only_item = build_mmd_render_item(replace(model, materials=(ground_only_skin,)), render_mode=MMD_RENDER_TOON)
    ground_only_group = ground_only_item["groups"][0]
    assert ground_only_group["pmx_ground_shadow"] is True
    assert ground_only_group["casts_self_shadow"] is False
    assert ground_only_group["receives_self_shadow"] is False

    eye = replace(model.materials[0], name="eye", flags=0x1F)
    eye_item = build_mmd_render_item(replace(model, materials=(eye,)), render_mode=MMD_RENDER_TOON)
    eye_group = eye_item["groups"][0]
    assert eye_group["material_class"] == MMD_MATERIAL_EYE
    assert eye_group["casts_self_shadow"] is False
    assert eye_group["receives_self_shadow"] is False
    assert eye_group["shadow_policy"] == "face_detail_layer"

    transparent_hair = replace(model.materials[0], name="front hair", diffuse=(0.4, 0.5, 0.8, 0.5), flags=0x1F)
    transparent_item = build_mmd_render_item(replace(model, materials=(transparent_hair,)), render_mode=MMD_RENDER_TOON)
    transparent_group = transparent_item["groups"][0]
    assert transparent_group["render_bucket"] == MMD_RENDER_BUCKET_TRANSPARENT
    assert transparent_group["casts_self_shadow"] is False
    assert transparent_group["receives_self_shadow"] is False
    assert transparent_group["shadow_policy"] == "transparent_layer"
    row = transparent_item["diagnostics"]["material_bucket_rows"][0]
    assert row["casts_self_shadow"] is False
    assert row["receives_self_shadow"] is False


def test_material_tuning_scales_mmd_shader_controls(tmp_path: Path) -> None:
    path = tmp_path / "model.pmx"
    path.write_bytes(_minimal_pmx())
    model = load_pmx(path)

    skin = replace(model.materials[0], name="skin face")
    tuned_skin = build_mmd_render_item(
        replace(model, materials=(skin,)),
        render_mode=MMD_RENDER_TOON,
        material_tuning={"skin_warmth": 0.5},
    )
    assert tuned_skin["groups"][0]["skin_warmth"] < 0.34

    hair = replace(model.materials[0], name="hair")
    tuned_hair = build_mmd_render_item(
        replace(model, materials=(hair,)),
        render_mode=MMD_RENDER_TOON,
        material_tuning={"hair_highlight": 1.5},
    )
    assert tuned_hair["groups"][0]["toon_highlight_strength"] > 0.34


def test_mmd_diagnostics_reports_motion_and_material_stats(tmp_path: Path) -> None:
    pmx_path = tmp_path / "tiny.pmx"
    pmx_path.write_bytes(_minimal_pmx())
    vmd_path = tmp_path / "tiny.vmd"
    vmd_path.write_bytes(_minimal_vmd())

    report = analyze_mmd_model(pmx_path, vmd_path, sample_frames=[0, 15, 30])
    assert report["ok"] is True
    assert report["model"]["vertices"] == 3
    assert report["render"]["draw_group_count"] == 1
    assert report["alpha_policy"]["uv_blend_group_count"] == 0
    assert report["alpha_policy"]["transparent_front_hair_count"] == 0
    assert report["motion_policy"]["curve_count"] == 0
    assert report["motion_policy"]["nonlinear_curve_count"] == 0
    assert report["animation"]["sample_count"] == 3
    assert report["animation"]["max_active_bones"] == 1
    assert report["animation"]["max_pose_delta"] >= 1.0

    text = format_mmd_report([report])
    assert "ok            : True" in text
    assert "pose_delta" in text


def test_mmd_diagnostics_lists_missing_texture_rows(tmp_path: Path) -> None:
    pmx_path = tmp_path / "tiny.pmx"
    pmx_path.write_bytes(_minimal_pmx())
    model = load_pmx(pmx_path)
    material = replace(model.materials[0], name="gem", texture_index=0)
    model = replace(model, textures=("tex/missing_gem.png",), materials=(material,))

    item = build_mmd_render_item(model)
    diagnostics = item["diagnostics"]

    assert diagnostics["missing_texture_count"] == 1
    assert diagnostics["missing_texture_rows"] == [
        {
            "material_index": 0,
            "name": "gem",
            "texture": str(tmp_path / "tex" / "missing_gem.png"),
        }
    ]
    assert diagnostics["missing_texture_paths"] == [str(tmp_path / "tex" / "missing_gem.png")]


def test_mmd_performance_line_summarizes_preview_diagnostics() -> None:
    line = format_mmd_performance_line(
        {
            "preview_refresh_ms": 12.34,
            "preview_estimated_fps": 81.0,
            "preview_pose_ms": 4.2,
            "preview_render_item_ms": 1.1,
            "pose_cache_size": 7,
            "pose_cache_limit": 32,
            "adaptive_ik_iterations": 3,
            "gpu_skinning": True,
            "mmd_vbo_cache_binds": 10,
            "mmd_vbo_cache_hits": 8,
            "mmd_vbo_cache_misses": 2,
        }
    )
    assert "Perf 12.3ms 81fps" in line
    assert "pose 4.2ms" in line
    assert "build 1.1ms" in line
    assert "cache 7/32" in line
    assert "IK 3" in line
    assert "vbo 8/10" in line
    assert line.endswith("GPU")

    fallback = format_mmd_performance_line(
        {
            "preview_refresh_ms": 20.0,
            "preview_estimated_fps": 50.0,
            "gpu_skinning_fallback_reason": "sdef_cpu_skinning_required",
        }
    )
    assert fallback.endswith("CPU(SDEF)")


def test_mmd_diagnostics_reports_vmd_interpolation_curves(tmp_path: Path) -> None:
    pmx_path = tmp_path / "tiny.pmx"
    pmx_path.write_bytes(_minimal_pmx())
    vmd_path = tmp_path / "curve.vmd"
    vmd_path.write_bytes(_curve_vmd())

    report = analyze_mmd_model(pmx_path, vmd_path, sample_frames=[0, 15, 30])
    assert report["motion_policy"]["curve_count"] == 4
    assert report["motion_policy"]["nonlinear_curve_count"] == 1
    assert report["motion_policy"]["max_linear_delta"] > 0.25
    assert "vmd_interpolation_curves" in report["feature_flags"]


def test_mmd_diagnostics_reports_front_hair_alpha_policy(tmp_path: Path) -> None:
    from PIL import Image

    pmx_path = tmp_path / "tiny.pmx"
    pmx_path.write_bytes(_minimal_pmx())
    texture_path = tmp_path / "hair_local_gradient.png"
    image = Image.new("RGBA", (32, 32), (255, 255, 255, 255))
    pixels = image.load()
    for y in range(32):
        pixels[0, y] = (255, 255, 255, 160)
    image.save(texture_path)

    model = load_pmx(pmx_path)
    material = replace(model.materials[0], name="front hair", texture_index=0)
    uvs = np.asarray([(0.0, 0.1), (0.0, 0.5), (0.0, 0.9)], dtype=np.float32)
    model = replace(model, textures=("hair_local_gradient.png",), materials=(material,), uvs=uvs)

    report = analyze_mmd_model(model, None, sample_frames=[0])
    alpha_policy = report["alpha_policy"]
    assert alpha_policy["uv_blend_group_count"] == 1
    assert alpha_policy["transparent_front_hair_count"] == 1
    assert alpha_policy["material_alpha_rows"][0]["uv_alpha_mode"] == "blend"
    assert alpha_policy["material_alpha_rows"][0]["draw_priority"] >= 70
    assert "uv_alpha_gradients" in report["feature_flags"]
    assert "transparent_front_hair" in report["feature_flags"]
    assert "mmd_front_hair_alpha_order_low" not in report["risk_codes"]


def test_mmd_regression_profile_reports_missing_material() -> None:
    profile = mmd_regression_profile("zzz_alice_sea_of_thyme")
    result = evaluate_mmd_regression_profile({"render": {"material_bucket_rows": []}}, str(profile["id"]))
    assert result["ok"] is False
    assert result["failure_count"] >= 1
    assert result["failures"][0]["reason"] == "missing_material"


@pytest.mark.skipif(
    not mmd_regression_profile_model_path("zzz_alice_sea_of_thyme").exists(),
    reason="local Alice Sea of Thyme MMD resource not present",
)
def test_zzz_alice_regression_profile_matches_local_material_policy() -> None:
    path = mmd_regression_profile_model_path("zzz_alice_sea_of_thyme")
    report = analyze_mmd_model(path, None, sample_frames=[0])
    result = evaluate_mmd_regression_profile(report, "zzz_alice_sea_of_thyme")
    assert result["ok"] is True, result["failures"]
    assert report["alpha_policy"]["uv_blend_group_count"] == 1
    assert report["alpha_policy"]["transparent_front_hair_count"] == 0


@pytest.mark.skipif(
    not mmd_regression_profile_model_path("cantarella_wavefile_cloth_motion").exists()
    or mmd_regression_profile_motion_path("cantarella_wavefile_cloth_motion") is None
    or not mmd_regression_profile_motion_path("cantarella_wavefile_cloth_motion").exists(),
    reason="local Cantarella MMD motion regression resources not present",
)
def test_cantarella_wavefile_regression_profile_exercises_cloth_motion() -> None:
    path = mmd_regression_profile_model_path("cantarella_wavefile_cloth_motion")
    motion_path = mmd_regression_profile_motion_path("cantarella_wavefile_cloth_motion")
    report = analyze_mmd_model(path, motion_path)
    result = evaluate_mmd_regression_profile(report, "cantarella_wavefile_cloth_motion")
    assert result["ok"] is True, result["failures"]
    assert report["animation"]["max_active_ik"] >= 1
    assert report["physics_policy"]["probe_rotation_bone_count"] >= 200


def test_sdef_path_reports_active_vertices(tmp_path: Path) -> None:
    pmx_path = tmp_path / "tiny.pmx"
    pmx_path.write_bytes(_minimal_pmx())
    vmd_path = tmp_path / "tiny.vmd"
    vmd_path.write_bytes(_minimal_vmd())

    model = load_pmx(pmx_path)
    weights = replace(
        model.weights,
        bone_indices=np.asarray([[0, 0, -1, -1]] * model.vertex_count, dtype=np.int32),
        bone_weights=np.asarray([[0.5, 0.5, 0.0, 0.0]] * model.vertex_count, dtype=np.float32),
        weight_types=np.asarray([3] * model.vertex_count, dtype=np.uint8),
        sdef_c=np.zeros((model.vertex_count, 3), dtype=np.float32),
        sdef_r0=np.zeros((model.vertex_count, 3), dtype=np.float32),
        sdef_r1=np.zeros((model.vertex_count, 3), dtype=np.float32),
    )
    model = replace(model, weights=weights)
    motion = load_vmd(vmd_path)

    pose = evaluate_model_pose(model, motion, 15.0)
    assert pose.active_sdef_count == model.vertex_count
    item = build_mmd_render_item(model, pose_geometry=pose)
    assert item["gpu_skinning"] is False
    assert item["diagnostics"]["sdef_cpu_skinning_required"] is True
    assert item["diagnostics"]["gpu_skinning_available"] is False
    assert item["diagnostics"]["gpu_skinning_fallback_reason"] == "sdef_cpu_skinning_required"

    report = analyze_mmd_model(model, motion, sample_frames=[15])
    assert report["weights"]["sdef"] == model.vertex_count
    assert report["render"]["sdef_cpu_skinning_required"] is True
    assert report["animation"]["max_active_sdef"] == model.vertex_count
    assert "sdef_cpu_skinning_required" in report["feature_flags"]
    assert "sdefcpu" in format_mmd_report([report])


def test_sdef_r0_r1_anchors_affect_deformation(tmp_path: Path) -> None:
    pmx_path = tmp_path / "tiny.pmx"
    pmx_path.write_bytes(_minimal_pmx())
    vmd_path = tmp_path / "child_rotate.vmd"
    vmd_path.write_bytes(_child_rotation_vmd())

    model = load_pmx(pmx_path)
    root = replace(model.bones[0], name="root", english_name="root", parent_index=-1, position=(0.0, 0.0, 0.0))
    child = replace(model.bones[0], name="child", english_name="child", parent_index=-1, position=(0.0, 0.0, 0.0))
    base_weights = replace(
        model.weights,
        bone_indices=np.asarray([[0, 1, -1, -1]] * model.vertex_count, dtype=np.int32),
        bone_weights=np.asarray([[0.5, 0.5, 0.0, 0.0]] * model.vertex_count, dtype=np.float32),
        weight_types=np.asarray([3] * model.vertex_count, dtype=np.uint8),
        sdef_c=np.zeros((model.vertex_count, 3), dtype=np.float32),
        sdef_r0=np.zeros((model.vertex_count, 3), dtype=np.float32),
        sdef_r1=np.zeros((model.vertex_count, 3), dtype=np.float32),
    )
    anchored_weights = replace(
        base_weights,
        sdef_r0=np.asarray([[0.0, 0.0, 0.0]] * model.vertex_count, dtype=np.float32),
        sdef_r1=np.asarray([[0.8, 0.25, 0.0]] * model.vertex_count, dtype=np.float32),
    )
    motion = load_vmd(vmd_path)
    without_anchors = evaluate_model_pose(replace(model, bones=(root, child), weights=base_weights), motion, 15.0)
    with_anchors = evaluate_model_pose(replace(model, bones=(root, child), weights=anchored_weights), motion, 15.0)
    assert with_anchors.active_sdef_count == model.vertex_count
    assert float(np.max(np.abs(with_anchors.positions - without_anchors.positions))) > 0.0001


def test_ik_solver_moves_effector_toward_target_after_topology_cache(tmp_path: Path) -> None:
    pmx_path = tmp_path / "tiny.pmx"
    pmx_path.write_bytes(_minimal_pmx())
    vmd_path = tmp_path / "ik.vmd"
    vmd_path.write_bytes(_ik_target_vmd())

    model = load_pmx(pmx_path)
    root = replace(
        model.bones[0],
        name="root",
        english_name="root",
        parent_index=-1,
        position=(0.0, 0.0, 0.0),
        ik=None,
    )
    knee = MMDBone(
        name="knee",
        english_name="knee",
        position=(0.0, 1.0, 0.0),
        parent_index=0,
        transform_layer=0,
        flags=0,
        tail_index=-1,
        tail_position=(0.0, 1.0, 0.0),
        inherit_parent_index=-1,
        inherit_weight=0.0,
    )
    foot = MMDBone(
        name="foot",
        english_name="foot",
        position=(0.0, 2.0, 0.0),
        parent_index=1,
        transform_layer=0,
        flags=0,
        tail_index=-1,
        tail_position=(0.0, 1.0, 0.0),
        inherit_parent_index=-1,
        inherit_weight=0.0,
    )
    ik_bone = MMDBone(
        name="ik",
        english_name="ik",
        position=(0.0, 2.0, 0.0),
        parent_index=-1,
        transform_layer=0,
        flags=0,
        tail_index=-1,
        tail_position=(0.0, 0.0, 0.0),
        inherit_parent_index=-1,
        inherit_weight=0.0,
        ik=MMDIK(
            target_index=2,
            iteration_count=12,
            angle_limit=0.55,
            links=(
                MMDIKLink(1, False, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
                MMDIKLink(0, False, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
            ),
        ),
    )
    weights = replace(
        model.weights,
        bone_indices=np.asarray([[2, -1, -1, -1]] * model.vertex_count, dtype=np.int32),
        bone_weights=np.asarray([[1.0, 0.0, 0.0, 0.0]] * model.vertex_count, dtype=np.float32),
        weight_types=np.asarray([0] * model.vertex_count, dtype=np.uint8),
    )
    model = replace(model, bones=(root, knee, foot, ik_bone), weights=weights)
    motion = load_vmd(vmd_path)

    without_ik = evaluate_model_pose(
        model,
        motion,
        10.0,
        enable_ik=False,
        enable_physics=False,
        skin_vertices=False,
    )
    with_ik = evaluate_model_pose(
        model,
        motion,
        10.0,
        enable_ik=True,
        enable_physics=False,
        max_ik_iterations=12,
        skin_vertices=False,
    )

    target = np.asarray((0.8, 1.5, 0.0), dtype=np.float32)
    rest_foot = np.append(np.asarray(model.bones[2].position, dtype=np.float32), 1.0)
    without_pos = (rest_foot @ without_ik.bone_matrices[2].T)[:3]
    with_pos = (rest_foot @ with_ik.bone_matrices[2].T)[:3]
    assert with_ik.active_ik_count == 1
    assert float(np.linalg.norm(with_pos - target)) < float(np.linalg.norm(without_pos - target))
    assert with_pos[0] > without_pos[0] + 0.05


def test_auto_frame_bounds_fits_tall_models_with_margin() -> None:
    bounds = bounds_from_min_max(
        np.asarray((-0.55, 0.0, -0.25), dtype=np.float32),
        np.asarray((0.55, 4.2, 0.25), dtype=np.float32),
    )
    fit = auto_frame_bounds(bounds, yaw=0.0, pitch=-4.0, aspect=16.0 / 9.0)

    assert 0.35 <= fit.zoom <= 2.2
    assert fit.coverage_y <= 0.97
    assert fit.coverage_y > 0.84
    assert abs(fit.offset_x) < 0.1


def test_framing_bounds_can_trim_sparse_outliers() -> None:
    core = np.asarray([(0.0, y, 0.0) for y in np.linspace(0.0, 2.0, 100)], dtype=np.float32)
    outliers = np.asarray([(0.0, 20.0, 0.0), (0.0, -10.0, 0.0)], dtype=np.float32)
    full = bounds_from_positions(np.concatenate([core, outliers], axis=0))
    trimmed = bounds_from_positions(np.concatenate([core, outliers], axis=0), trim_percentile=2.0)

    assert full["size"][1] > 25.0
    assert trimmed["size"][1] < 3.0


def test_decimated_physics_reuses_offsets_between_solver_ticks() -> None:
    class _Backend:
        def __init__(self) -> None:
            self.calls = 0

        def reset(self) -> None:
            self.calls = 0

        def offsets_for(self, _model, _globals, frame: float):
            self.calls += 1
            return {0: np.asarray((frame, 0.0, 0.0), dtype=np.float32)}, 1

    backend = _Backend()
    wrapped = DecimatedPhysicsBackend(backend, update_interval_frames=2.0)

    first, _ = wrapped.offsets_for(None, [], 0.0)  # type: ignore[arg-type]
    second, _ = wrapped.offsets_for(None, [], 1.0)  # type: ignore[arg-type]
    third, _ = wrapped.offsets_for(None, [], 2.0)  # type: ignore[arg-type]

    assert backend.calls == 2
    assert np.allclose(first[0], second[0])
    assert not np.allclose(second[0], third[0])


def test_decimated_physics_smooths_solver_offset_jumps() -> None:
    class _Backend:
        def __init__(self) -> None:
            self.calls = 0

        def reset(self) -> None:
            self.calls = 0

        def offsets_for(self, _model, _globals, frame: float):
            self.calls += 1
            return {0: np.asarray((frame, 0.0, 0.0), dtype=np.float32)}, 1

    backend = _Backend()
    wrapped = DecimatedPhysicsBackend(backend, update_interval_frames=2.0, smoothing_response=0.5)

    first, _ = wrapped.offsets_for(None, [], 0.0)  # type: ignore[arg-type]
    held, _ = wrapped.offsets_for(None, [], 1.0)  # type: ignore[arg-type]
    smoothed, _ = wrapped.offsets_for(None, [], 2.0)  # type: ignore[arg-type]
    later, _ = wrapped.offsets_for(None, [], 4.0)  # type: ignore[arg-type]

    assert backend.calls == 3
    assert np.allclose(first[0], (0.0, 0.0, 0.0))
    assert np.allclose(held[0], first[0])
    assert np.allclose(smoothed[0], (1.0, 0.0, 0.0))
    assert np.allclose(later[0], (2.5, 0.0, 0.0))


def test_vmd_camera_rotation_interpolates_shortest_angle() -> None:
    curve = VMDBezier()
    interpolation = VMDCameraInterpolation(curve, curve, curve, curve, curve, curve)
    motion = VMDMotion(
        path=Path("camera.vmd"),
        header="Vocaloid Motion Data 0002",
        model_name="camera",
        bone_frames={},
        morph_frames={},
        camera_frames=(
            VMDCameraFrame(0, -35.0, (0.0, 0.0, 0.0), (0.0, math.radians(179.0), 0.0), 45.0, True, interpolation),
            VMDCameraFrame(30, -35.0, (0.0, 0.0, 0.0), (0.0, math.radians(-179.0), 0.0), 45.0, True, interpolation),
        ),
        max_frame=30,
    )

    mid = camera_at(motion, 15.0)
    assert mid is not None
    assert abs(abs(mid.rotation[1]) - math.pi) < 0.05


def test_transparent_material_priority_draws_eye_after_hair_at_same_depth(tmp_path: Path) -> None:
    path = tmp_path / "tiny.pmx"
    path.write_bytes(_minimal_pmx())
    model = load_pmx(path)
    positions = np.asarray(
        [
            (-1.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (-0.8, 0.1, 0.0),
            (0.8, 0.1, 0.0),
            (0.0, 0.9, 0.0),
        ],
        dtype=np.float32,
    )
    normals = np.asarray([(0.0, 0.0, 1.0)] * 6, dtype=np.float32)
    uvs = np.asarray([(0.0, 0.0), (1.0, 0.0), (0.5, 1.0)] * 2, dtype=np.float32)
    indices = np.asarray([0, 1, 2, 3, 4, 5], dtype=np.int32)
    eye = replace(model.materials[0], name="eye highlight", diffuse=(0.8, 0.9, 1.0, 0.5), surface_count=3)
    hair = replace(model.materials[0], name="hair", diffuse=(0.2, 0.2, 0.8, 0.5), surface_count=3)
    model = replace(
        model,
        positions=positions,
        normals=normals,
        uvs=uvs,
        indices=indices,
        materials=(eye, hair),
        bounds_min=(-1.0, 0.0, 0.0),
        bounds_max=(1.0, 1.0, 0.0),
    )

    item = build_mmd_render_item(model, render_mode=MMD_RENDER_TOON, yaw=0.0, pitch=0.0)
    assert [group["material_index"] for group in item["groups"]] == [1, 0]
    assert item["groups"][-1]["draw_priority"] > item["groups"][0]["draw_priority"]


def test_transparent_front_hair_draws_after_face_details_at_same_depth(tmp_path: Path) -> None:
    path = tmp_path / "tiny.pmx"
    path.write_bytes(_minimal_pmx())
    model = load_pmx(path)
    positions = np.asarray(
        [
            (-1.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (-0.9, 0.05, 0.0),
            (0.9, 0.05, 0.0),
            (0.0, 0.95, 0.0),
            (-0.8, 0.1, 0.0),
            (0.8, 0.1, 0.0),
            (0.0, 0.9, 0.0),
        ],
        dtype=np.float32,
    )
    normals = np.asarray([(0.0, 0.0, 1.0)] * 9, dtype=np.float32)
    uvs = np.asarray([(0.0, 0.0), (1.0, 0.0), (0.5, 1.0)] * 3, dtype=np.float32)
    indices = np.arange(9, dtype=np.int32)
    front_hair = replace(model.materials[0], name="front hair", diffuse=(0.2, 0.3, 0.8, 0.5), surface_count=3)
    eye = replace(model.materials[0], name="eye highlight", diffuse=(0.8, 0.9, 1.0, 0.5), surface_count=3)
    brow = replace(model.materials[0], name="eyebrow", diffuse=(0.1, 0.08, 0.06, 0.5), surface_count=3)
    model = replace(
        model,
        positions=positions,
        normals=normals,
        uvs=uvs,
        indices=indices,
        materials=(front_hair, eye, brow),
        bounds_min=(-1.0, 0.0, 0.0),
        bounds_max=(1.0, 1.0, 0.0),
    )

    item = build_mmd_render_item(model, render_mode=MMD_RENDER_TOON, yaw=0.0, pitch=0.0)
    assert [group["name"] for group in item["groups"]] == ["eye highlight", "eyebrow", "front hair"]
    assert item["groups"][-1]["material_class"] == MMD_MATERIAL_HAIR
    assert item["groups"][-1]["draw_priority"] > item["groups"][1]["face_layer_priority"]


def test_zzz_eye_layers_use_semantic_draw_order(tmp_path: Path) -> None:
    path = tmp_path / "tiny.pmx"
    path.write_bytes(_minimal_pmx())
    model = load_pmx(path)
    positions = np.asarray(
        [
            (-0.5, 0.0, -0.04),
            (0.5, 0.0, -0.04),
            (0.0, 1.0, -0.04),
        ]
        * 5,
        dtype=np.float32,
    )
    normals = np.asarray([(0.0, 0.0, 1.0)] * 15, dtype=np.float32)
    uvs = np.asarray([(0.0, 0.0), (1.0, 0.0), (0.5, 1.0)] * 5, dtype=np.float32)
    indices = np.arange(15, dtype=np.int32)
    names = ("\u767d\u76ee", "\u76ee\u5f71", "\u76ee", "\u76ee\u5149", "\u776b\u7709")
    materials = tuple(
        replace(
            model.materials[0],
            name=name,
            diffuse=(1.0, 1.0, 1.0, 0.45),
            surface_count=3,
        )
        for name in names
    )
    model = replace(
        model,
        positions=positions,
        normals=normals,
        uvs=uvs,
        indices=indices,
        materials=materials,
        bounds_min=(-0.5, 0.0, -0.04),
        bounds_max=(0.5, 1.0, -0.04),
    )

    item = build_mmd_render_item(model, render_mode=MMD_RENDER_TOON, yaw=0.0, pitch=0.0)
    ordered_names = [group["name"] for group in item["groups"]]
    assert ordered_names == ["\u767d\u76ee", "\u76ee\u5f71", "\u76ee", "\u76ee\u5149", "\u776b\u7709"]
    assert [group["face_layer_priority"] for group in item["groups"]] == [20, 30, 40, 60, 70]
