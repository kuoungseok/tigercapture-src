from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest


def test_painter_3d_blockout_projects_and_renders_gpu_ready_preview(tmp_path: Path) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from app.painter_3d_blockout import (
        add_blockout_primitive,
        default_blockout_scene,
        project_blockout_scene,
        render_blockout_scene_qimage,
    )

    scene = default_blockout_scene()
    scene = add_blockout_primitive(scene, kind="box", name="Room Block", sx=2.0, sy=1.2, sz=1.4)
    scene = add_blockout_primitive(scene, kind="box", name="Wide Floor Mass", z=-1.1, sx=3.0, sy=0.2, sz=1.8)
    scene = add_blockout_primitive(scene, kind="arch", name="Door Arch", x=-1.0, z=0.8)

    projection = project_blockout_scene(scene, 640, 360)
    assert projection["schema"] == "tigerstudio.painter.3d_blockout.projection.v1"
    assert projection["model_contract"]["physical_camera_claim"] is False
    assert projection["model_contract"]["external_3d_application_parity_claim"] is False
    assert projection["scene"]["primitive_count"] == 3
    assert projection["face_count"] > 0
    assert projection["edge_count"] > 0
    assert projection["scene"]["material_lit"] is True
    assert projection["scene"]["show_shadows"] is True
    assert projection["scene"]["show_floor"] is True
    assert projection["scene"]["light_yaw_degrees"] == 45.0
    assert projection["scene"]["light_pitch_degrees"] == 45.0
    assert projection["shadows"]
    cube_shadow = next(
        shadow
        for shadow in projection["shadows"]
        if shadow["primitive_id"] == "blockout:1"
    )
    assert cube_shadow["kind"] == "box"
    assert len(cube_shadow["polygon"]) >= 4
    assert cube_shadow["depth"] > 0.0
    assert projection["floor_tiles"]
    assert all(tile["point_depths"] for tile in projection["floor_tiles"])
    assert projection["depth_range"]["far"] > projection["depth_range"]["near"]
    assert {tile["world_tile_size"] for tile in projection["floor_tiles"]} == {1.0}
    assert "box" in projection["scene"]["supported_primitives"]
    assert "arch" in projection["scene"]["supported_primitives"]

    image = render_blockout_scene_qimage(scene, 320, 180)
    assert image.width() == 320
    assert image.height() == 180
    out = tmp_path / "blockout_preview.png"
    assert image.save(str(out))
    assert out.exists()
    with pytest.raises(ValueError, match="viewport width must be positive"):
        project_blockout_scene(scene, 0, 360)
    with pytest.raises(TypeError, match="viewport height must be an integer"):
        render_blockout_scene_qimage(scene, 320, 180.5)


def test_painter_opengl_status_is_remote_safe() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.painter_opengl import painter_opengl_status

    app = QApplication.instance() or QApplication([])
    assert app is not None
    status = painter_opengl_status()
    assert status["schema"] == "tigerstudio.painter.opengl.status.v1"
    assert status["renderer"] == "painter_blockout_opengl_offscreen_v1"
    assert status["default_policy"] == "auto_opengl_with_qpainter_fallback"
    assert status["remote_safe"] is True
    assert status["fallback_on_context_failure"] is True
    assert status["available"] is False
    assert status["active_backend"] == status["fallback_renderer"]
    assert "dependency_ready" in status
    assert "candidate_backend" in status
    assert status["surfaces"]["blockout_preview"] == "opengl_offscreen_if_available"


def test_painter_opengl_import_failure_is_typed_and_selects_cpu(monkeypatch) -> None:
    import builtins
    from app.painter_opengl import (
        PAINTER_CANVAS_FALLBACK_RENDERER_ID,
        painter_canvas_opengl_status,
        painter_opengl_status,
    )

    original_import = builtins.__import__

    def fail_opengl(name, *args, **kwargs):
        if name == "OpenGL" or name.startswith("OpenGL."):
            raise ModuleNotFoundError("injected PyOpenGL absence")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fail_opengl)
    blockout = painter_opengl_status()
    canvas = painter_canvas_opengl_status()
    assert blockout["available"] is False
    assert blockout["active_backend"] == blockout["fallback_renderer"]
    assert blockout["pyopengl_error"] == (
        "ModuleNotFoundError: injected PyOpenGL absence"
    )
    assert canvas["available"] is False
    assert canvas["active_backend"] == PAINTER_CANVAS_FALLBACK_RENDERER_ID
    assert canvas["pyopengl_error"] == (
        "ModuleNotFoundError: injected PyOpenGL absence"
    )


def test_canvas_status_survives_capability_probe_failure(monkeypatch) -> None:
    from app import painter_opengl

    def fail_capabilities():
        raise RuntimeError("injected capability implementation failure")

    monkeypatch.setattr(
        painter_opengl, "painter_canvas_gpu_capabilities", fail_capabilities
    )
    status = painter_opengl.painter_canvas_opengl_status()
    assert status["available"] is False
    assert status["active_backend"] == status["fallback_renderer"]
    assert status["capabilities"]["persistent_stroke_atlas"]["enabled"] is False
    assert status["supported_first_pass"] == {}
    assert status["capabilities_error"] == (
        "RuntimeError: injected capability implementation failure"
    )


def test_gl_cleanup_failure_is_typed_and_preserves_primary_error() -> None:
    from app import painter_opengl

    painter_opengl._GL_CLEANUP_STATUS.update(
        {
            "failure_count": 0,
            "last_operation": "",
            "last_error": "",
            "primary_error_preserved": False,
        }
    )

    def fail_cleanup() -> None:
        raise RuntimeError("injected FBO release failure")

    primary = ValueError("injected render failure")
    try:
        raise primary
    except ValueError:
        assert painter_opengl._best_effort_gl_cleanup(
            "canvas_framebuffer_release", fail_cleanup
        ) is False

    status = painter_opengl.painter_opengl_status()["cleanup"]
    assert status == {
        "failure_count": 1,
        "last_operation": "canvas_framebuffer_release",
        "last_error": "RuntimeError: injected FBO release failure",
        "primary_error_preserved": True,
    }
    assert any(
        "canvas_framebuffer_release" in note
        and "RuntimeError: injected FBO release failure" in note
        for note in getattr(primary, "__notes__", [])
    )


def test_retained_compositors_release_resources_when_rendering_fails() -> None:
    from app import painter_opengl

    class FakeFbo:
        def __init__(self, *_args) -> None:
            self.releases = 0

        def isValid(self) -> bool:
            return True

        def bind(self) -> bool:
            return True

        def release(self) -> None:
            self.releases += 1

    class FakeUploader:
        GL = SimpleNamespace(
            GL_DEPTH_TEST=1,
            GL_BLEND=2,
            GL_SRC_ALPHA=3,
            GL_ONE_MINUS_SRC_ALPHA=4,
            GL_COLOR_BUFFER_BIT=5,
            GL_PROJECTION=6,
            GL_MODELVIEW=7,
            GL_TEXTURE_2D=8,
            GL_QUADS=9,
        )

        def __init__(self) -> None:
            self.fbos: list[FakeFbo] = []
            self.deleted: list[int] = []
            self.next_handle = 40

        def FBO(self, *_args):
            fbo = FakeFbo()
            self.fbos.append(fbo)
            return fbo

        def _current(self) -> None:
            return None

        def _clear_qt_boundary_errors(self) -> None:
            return None

        def _gl(self, *_args) -> None:
            return None

        def __call__(self, *_args) -> int:
            self.next_handle += 1
            return self.next_handle

        def delete(self, handle: int) -> None:
            self.deleted.append(handle)

        def _read_rgba(self, *_args):
            raise RuntimeError("injected retained readback failure")

    normal = FakeUploader()
    with pytest.raises(RuntimeError, match="retained readback failure"):
        painter_opengl.PainterRetainedGLTileUploader.composite_normal_layers(
            normal, [(object(), 1.0), (object(), 0.5)], 32, 24
        )
    assert normal.deleted == [41, 42]
    assert normal.fbos[0].releases == 1

    tiles = FakeUploader()
    tiles.display_composites = 0
    tiles.display_texture_reads = 0
    tiles.display_readback_bytes = 0
    missing = SimpleNamespace(gpu_handle=0, image=SimpleNamespace())
    with pytest.raises(
        painter_opengl.PainterOpenGLUnavailable,
        match="no GPU texture handle",
    ):
            painter_opengl.PainterRetainedGLTileUploader.composite_tile_records(
                tiles, [(0, 0, missing)], 32, 24, 32
            )
    assert tiles.fbos[0].releases == 1


def test_retained_uploader_close_continues_after_texture_destroy_failure() -> None:
    from app import painter_opengl

    calls: list[str] = []

    class Texture:
        def __init__(self, name: str, fail: bool = False) -> None:
            self.name = name
            self.fail = fail

        def destroy(self) -> None:
            calls.append(self.name)
            if self.fail:
                raise RuntimeError("injected retained texture destroy failure")

    uploader = object.__new__(painter_opengl.PainterRetainedGLTileUploader)
    uploader.handles = {11, 12}
    uploader.texture_objects = {
        11: Texture("first", fail=True),
        12: Texture("second"),
    }
    uploader.validation_fbo = object()
    uploader.fbo = 1
    uploader.surface = SimpleNamespace(destroy=lambda: calls.append("surface"))
    uploader.context = SimpleNamespace(
        makeCurrent=lambda _surface: True,
        doneCurrent=lambda: calls.append("context"),
    )

    uploader.close()

    assert calls == ["first", "second", "context", "surface"]
    assert uploader.handles == set()
    assert uploader.texture_objects == {}
    assert uploader.validation_fbo is None
    assert uploader.fbo == 0
    status = painter_opengl.painter_opengl_cleanup_status()
    assert status["last_operation"] == "retained_texture_destroy"
    assert status["last_error"] == (
        "RuntimeError: injected retained texture destroy failure"
    )


def test_canvas_session_close_destroys_surface_after_done_current_failure() -> None:
    from app import painter_opengl

    calls: list[str] = []
    session = painter_opengl._PainterCanvasOffscreenSession()

    def fail_done_current() -> None:
        calls.append("context")
        raise RuntimeError("injected doneCurrent failure")

    session.context = SimpleNamespace(doneCurrent=fail_done_current)
    session.surface = SimpleNamespace(destroy=lambda: calls.append("surface"))
    session.close()

    assert calls == ["context", "surface"]
    assert session.closed is True
    assert session.context is None
    assert session.surface is None
    status = painter_opengl.painter_opengl_cleanup_status()
    assert status["last_operation"] == "canvas_session_context_done_current"
    assert status["last_error"] == "RuntimeError: injected doneCurrent failure"


def test_context_create_failure_preserves_product_error_when_surface_destroy_fails(
    monkeypatch,
) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app import painter_3d_blockout, painter_opengl

    assert QApplication.instance() or QApplication([])
    destroyed: list[str] = []

    class Surface:
        def setFormat(self, _format) -> None:
            return None

        def create(self) -> None:
            return None

        def isValid(self) -> bool:
            return True

        def destroy(self) -> None:
            destroyed.append("surface")
            raise RuntimeError("injected surface destroy failure")

    class Context:
        def setFormat(self, _format) -> None:
            return None

        def create(self) -> bool:
            return False

    monkeypatch.setattr(painter_opengl, "QOffscreenSurface", Surface)
    monkeypatch.setattr(painter_opengl, "QOpenGLContext", Context)

    with pytest.raises(
        painter_opengl.PainterOpenGLUnavailable,
        match="could not create a context",
    ):
        painter_opengl._make_offscreen_context()
    assert destroyed == ["surface"]

    destroyed.clear()
    monkeypatch.setattr(
        painter_3d_blockout,
        "project_blockout_scene",
        lambda *_args, **_kwargs: {},
    )
    with pytest.raises(
        painter_opengl.PainterOpenGLUnavailable,
        match="could not create a context",
    ):
        painter_opengl.render_blockout_scene_opengl_qimage({}, 2, 2)
    assert destroyed == ["surface"]
    status = painter_opengl.painter_opengl_cleanup_status()
    assert status["last_error"] == "RuntimeError: injected surface destroy failure"


def test_painter_canvas_gpu_path_reports_remote_safe_renderer() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.drawing import PaintDialog, Stroke, create_blank_paint_pixmap

    app = QApplication.instance() or QApplication([])
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(320, 180, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.show()
    app.processEvents()

    dialog.canvas.add_stroke_direct(
        Stroke(
            points=[(0.1, 0.2), (0.35, 0.5), (0.7, 0.3)],
            color=(48, 150, 255),
            opacity=220,
            width_px=6.0,
            brush_style="round",
        )
    )
    dialog.canvas.grab()
    app.processEvents()

    canvas_status = dialog.painter_action_state()["gpu"]["canvas_renderer"]
    assert canvas_status["remote_safe"] is True
    assert canvas_status["active"] in {"opengl", "qpainter"}
    assert canvas_status["renderer"] in {
        "painter_canvas_opengl_persistent_stroke_atlas_v1",
        "painter_canvas_qpainter_strokes_v1",
    }
    if canvas_status["active"] == "opengl":
        assert canvas_status["source_renderer"] == "painter_canvas_opengl_stroke_fbo_v1"

    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_painter_canvas_stroke_atlas_reuses_signature(monkeypatch) -> None:
    from PySide6.QtGui import QImage

    import app.painter_opengl as painter_opengl

    calls = {"count": 0}

    def fake_render(*_args, width: int, height: int, **_kwargs):
        calls["count"] += 1
        image = QImage(max(1, int(width)), max(1, int(height)), QImage.Format.Format_RGBA8888)
        image.fill(0)
        return image, {
            "renderer": painter_opengl.PAINTER_CANVAS_OPENGL_RENDERER_ID,
            "active": "opengl",
            "fallback": False,
            "size": [int(width), int(height)],
        }

    monkeypatch.setattr(painter_opengl, "render_canvas_strokes_opengl_qimage", fake_render)
    atlas = painter_opengl.PainterCanvasStrokeAtlas()
    stroke = SimpleNamespace(
        points=[(0.1, 0.2), (0.4, 0.5)],
        color=(255, 255, 255),
        opacity=255,
        width_px=4.0,
        brush_style="round",
        layer_id="paint-layer-1",
        start_ms=0,
        end_ms=None,
        closed_path=False,
    )

    image_1, report_1 = atlas.render([stroke], width=320, height=180, time_ms=0)
    image_2, report_2 = atlas.render([stroke], width=320, height=180, time_ms=0)

    assert calls["count"] == 1
    assert image_1 is image_2
    assert report_1["renderer"] == "painter_canvas_opengl_persistent_stroke_atlas_v1"
    assert report_1["source_renderer"] == "painter_canvas_opengl_stroke_fbo_v1"
    assert report_1["readback"] is True
    assert report_2["cache_hit"] is True
    assert report_2["readback"] is False


def test_painter_3d_blockout_crud_validates_inputs_and_rejects_duplicate_ids() -> None:
    from app.painter_3d_blockout import (
        add_blockout_primitive,
        align_blockout_primitive_to_ground,
        apply_blockout_camera_preset,
        default_blockout_scene,
        delete_blockout_primitive,
        duplicate_blockout_primitive,
        set_blockout_snap,
        snap_blockout_primitive_to_grid,
        update_blockout_primitive,
    )

    for invalid in (
        {"kind": "unknown"},
        {"color": "bad"},
        {"opacity": 9.0},
        {"x": float("nan")},
        {"sx": 0.001},
        {"wireframe": 1},
    ):
        with pytest.raises((TypeError, ValueError)):
            add_blockout_primitive(default_blockout_scene(), **invalid)

    scene = add_blockout_primitive(
        default_blockout_scene(),
        primitive_id="blockout:room",
        kind="box",
        color="#F2F2F2",
        opacity=1.0,
    )
    primitive = scene.to_dict()["primitives"][0]
    assert primitive["kind"] == "box"
    assert primitive["color"] == "#F2F2F2"
    assert primitive["opacity"] == 1.0

    try:
        add_blockout_primitive(scene, primitive_id="blockout:room")
    except ValueError as exc:
        assert "already exists" in str(exc)
    else:
        raise AssertionError("duplicate primitive id should fail")

    scene = update_blockout_primitive(scene, "blockout:room", kind="arch", x=1.5, ry=35, sx=2.0)
    updated = scene.to_dict()["primitives"][0]
    assert updated["kind"] == "arch"
    assert updated["position"][0] == 1.5
    assert updated["rotation"][1] == 35.0
    assert updated["scale"][0] == 2.0

    scene = duplicate_blockout_primitive(scene, "blockout:room", offset=(0.5, 0.0, 0.25))
    rows = scene.to_dict()["primitives"]
    assert len(rows) == 2
    assert rows[1]["name"].endswith("Copy")
    assert rows[1]["position"][0] == rows[0]["position"][0] + 0.5

    scene = update_blockout_primitive(scene, "blockout:room", y=-3.0, sx=2.0, sy=1.5, sz=1.0)
    scene = align_blockout_primitive_to_ground(scene, "blockout:room")
    grounded = scene.to_dict()["primitives"][0]
    assert grounded["position"][2] == 0.0

    scene = update_blockout_primitive(scene, "blockout:room", x=0.26, y=0.74, z=1.26, rx=11, ry=17)
    scene = snap_blockout_primitive_to_grid(scene, "blockout:room", grid_size=0.5)
    snapped = scene.to_dict()["primitives"][0]
    assert snapped["position"] == [0.5, 0.5, 1.5]
    assert snapped["rotation"][0] == 10.0
    assert snapped["rotation"][1] == 15.0

    scene = set_blockout_snap(scene, True)
    assert scene.to_dict()["snap_to_grid"] is True
    with pytest.raises(TypeError):
        set_blockout_snap(scene, 1)
    for invalid_step in (True, 0.0, float("nan"), float("inf")):
        with pytest.raises((TypeError, ValueError)):
            snap_blockout_primitive_to_grid(
                scene, "blockout:room", grid_size=invalid_step
            )

    scene = apply_blockout_camera_preset(scene, "top")
    assert scene.to_dict()["camera"]["pitch_degrees"] == -82.0
    with pytest.raises((TypeError, ValueError)):
        apply_blockout_camera_preset(scene, "right")

    scene = delete_blockout_primitive(scene, "blockout:room")
    assert scene.to_dict()["primitive_count"] == 1


def test_malformed_custom_blockout_ids_do_not_claim_generated_index() -> None:
    from app.painter_3d_blockout import BlockoutPrimitive, BlockoutScene

    scene = BlockoutScene(
        primitives=(
            BlockoutPrimitive(id="blockout:room"),
            BlockoutPrimitive(id="custom:999999"),
            BlockoutPrimitive(id="blockout:-4"),
            BlockoutPrimitive(id="blockout:7"),
        ),
        next_index=2,
    ).normalized()
    assert scene.next_index == 8


def test_blockout_malformed_primitive_and_light_restore_is_finite_and_bounded() -> None:
    import json

    from app.painter_3d_blockout import (
        BLOCKOUT_LIGHT_PITCH_MAX_DEGREES,
        BLOCKOUT_LIGHT_YAW_MIN_DEGREES,
        BLOCKOUT_PRIMITIVE_POSITION_MAX,
        BLOCKOUT_PRIMITIVE_ROTATION_MIN_DEGREES,
        BLOCKOUT_PRIMITIVE_SCALE_MAX,
        blockout_scene_from_dict,
        project_blockout_scene,
    )

    scene = blockout_scene_from_dict(
        {
            "primitives": [{
                "id": "blockout:1",
                "position": [1e308, float("nan"), float("inf")],
                "rotation": [float("-inf"), -1e308, "bad"],
                "scale": [1e308, float("nan"), -1e308],
                "opacity": float("nan"),
                "color": "#GGGGGG",
                "kind": "torus",
            }],
            "grid_size": float("nan"),
            "light_yaw_degrees": -1e308,
            "light_pitch_degrees": 1e308,
        }
    )
    payload = scene.to_dict()
    primitive = payload["primitives"][0]
    assert primitive["position"] == [BLOCKOUT_PRIMITIVE_POSITION_MAX, 0.0, 0.0]
    assert primitive["rotation"] == [0.0, BLOCKOUT_PRIMITIVE_ROTATION_MIN_DEGREES, 0.0]
    assert primitive["scale"] == [BLOCKOUT_PRIMITIVE_SCALE_MAX, 1.0, BLOCKOUT_PRIMITIVE_SCALE_MAX]
    assert primitive["color"] == "#F2F2F2"
    assert primitive["kind"] == "box"
    assert payload["light_yaw_degrees"] == BLOCKOUT_LIGHT_YAW_MIN_DEGREES
    assert payload["light_pitch_degrees"] == BLOCKOUT_LIGHT_PITCH_MAX_DEGREES
    json.dumps(payload, allow_nan=False)
    json.dumps(project_blockout_scene(scene, 640, 360), allow_nan=False)


def test_painter_3d_blockout_camera_updates_fov_and_pan() -> None:
    from app.painter_3d_blockout import (
        add_blockout_primitive,
        default_blockout_scene,
        screen_to_blockout_ground,
        update_blockout_camera,
    )

    scene = add_blockout_primitive(default_blockout_scene(), kind="box", sx=2.0)
    scene = update_blockout_camera(scene, yaw_degrees=18, pitch_degrees=-8, target_x=0.25, distance=4.5, fov_degrees=33)
    camera = scene.to_dict()["camera"]
    assert camera["yaw_degrees"] == 18.0
    assert camera["pitch_degrees"] == -8.0
    assert camera["target"][0] == 0.25
    assert camera["distance"] == 4.5
    assert camera["fov_degrees"] == 33.0
    world = screen_to_blockout_ground(scene, 320, 250, 640, 360)
    assert len(world) == 3
    assert abs(world[2]) < 0.0001


def test_blockout_camera_direct_update_is_strict_but_restore_is_finite() -> None:
    import json

    from app.painter_3d_blockout import (
        BLOCKOUT_CAMERA_DEFAULT_DISTANCE,
        BLOCKOUT_CAMERA_DEFAULT_FOV_DEGREES,
        BLOCKOUT_CAMERA_DEFAULT_PITCH_DEGREES,
        BLOCKOUT_CAMERA_DEFAULT_TARGET,
        BLOCKOUT_CAMERA_DEFAULT_YAW_DEGREES,
        BLOCKOUT_CAMERA_FOV_MAX_DEGREES,
        BLOCKOUT_CAMERA_FOV_MIN_DEGREES,
        BLOCKOUT_CAMERA_MAX_DISTANCE,
        BLOCKOUT_CAMERA_MIN_DISTANCE,
        BLOCKOUT_CAMERA_PITCH_MIN_DEGREES,
        BLOCKOUT_CAMERA_TARGET_MAX,
        BLOCKOUT_CAMERA_TARGET_MIN,
        BLOCKOUT_CAMERA_YAW_MAX_DEGREES,
        add_blockout_primitive,
        blockout_scene_from_dict,
        default_blockout_scene,
        project_blockout_scene,
        update_blockout_camera,
    )

    for payload in (
        {},
        {"yaw_degrees": True},
        {"yaw_degrees": float("nan")},
        {"distance": float("inf")},
        {"target_x": float("-inf")},
        {"target_x": 1e308},
        {"distance": 1e308},
        {"fov_degrees": float("nan")},
        {"yaw": 1.0, "yaw_degrees": 2.0},
        {"unknown": 1.0},
    ):
        with pytest.raises((TypeError, ValueError)):
            update_blockout_camera(default_blockout_scene(), **payload)

    restored = blockout_scene_from_dict(
        {
            "camera": {
                "yaw_degrees": float("nan"),
                "pitch_degrees": True,
                "distance": float("inf"),
                "target": [float("inf"), False, "bad"],
                "fov_degrees": float("nan"),
            }
        }
    ).to_dict()
    assert restored["camera"] == {
        "yaw_degrees": BLOCKOUT_CAMERA_DEFAULT_YAW_DEGREES,
        "pitch_degrees": BLOCKOUT_CAMERA_DEFAULT_PITCH_DEGREES,
        "distance": BLOCKOUT_CAMERA_DEFAULT_DISTANCE,
        "target": list(BLOCKOUT_CAMERA_DEFAULT_TARGET),
        "fov_degrees": BLOCKOUT_CAMERA_DEFAULT_FOV_DEGREES,
    }
    json.dumps(restored, allow_nan=False)

    extreme_restore = blockout_scene_from_dict(
        {
            "camera": {
                "yaw_degrees": 1e308,
                "pitch_degrees": -1e308,
                "distance": 1e308,
                "target": [1e308, -1e308, 1e308],
                "fov_degrees": 42.0,
            }
        }
    )
    extreme_camera = extreme_restore.to_dict()["camera"]
    assert extreme_camera["yaw_degrees"] == BLOCKOUT_CAMERA_YAW_MAX_DEGREES
    assert extreme_camera["pitch_degrees"] == BLOCKOUT_CAMERA_PITCH_MIN_DEGREES
    assert extreme_camera["distance"] == BLOCKOUT_CAMERA_MAX_DISTANCE
    assert extreme_camera["target"] == [
        BLOCKOUT_CAMERA_TARGET_MAX,
        BLOCKOUT_CAMERA_TARGET_MIN,
        BLOCKOUT_CAMERA_TARGET_MAX,
    ]
    json.dumps(
        project_blockout_scene(
            add_blockout_primitive(extreme_restore, kind="box"), 8192, 8192
        ),
        allow_nan=False,
    )

    clamped_restore = blockout_scene_from_dict(
        {
            "camera": {
                "yaw_degrees": 0.0,
                "pitch_degrees": 0.0,
                "distance": -100.0,
                "target": [0.0, 0.0, 0.0],
                "fov_degrees": 999.0,
            }
        }
    ).to_dict()["camera"]
    assert clamped_restore["distance"] == BLOCKOUT_CAMERA_MIN_DISTANCE
    assert clamped_restore["fov_degrees"] == BLOCKOUT_CAMERA_FOV_MAX_DEGREES
    assert clamped_restore["yaw_degrees"] == 0.0
    assert clamped_restore["target"] == [0.0, 0.0, 0.0]

    endpoints = update_blockout_camera(
        default_blockout_scene(),
        yaw_degrees=0.0,
        pitch_degrees=0.0,
        distance=BLOCKOUT_CAMERA_MIN_DISTANCE,
        target_x=0.0,
        target_y=0.0,
        target_z=0.0,
        fov_degrees=BLOCKOUT_CAMERA_FOV_MIN_DEGREES,
    ).to_dict()["camera"]
    assert endpoints["fov_degrees"] == BLOCKOUT_CAMERA_FOV_MIN_DEGREES
    assert endpoints["target"] == [0.0, 0.0, 0.0]
    assert update_blockout_camera(
        default_blockout_scene(),
        fov_degrees=BLOCKOUT_CAMERA_FOV_MAX_DEGREES,
    ).to_dict()["camera"]["fov_degrees"] == BLOCKOUT_CAMERA_FOV_MAX_DEGREES

    endpoint_scene = add_blockout_primitive(default_blockout_scene(), kind="box")
    for camera_update in (
        {"yaw_degrees": BLOCKOUT_CAMERA_YAW_MAX_DEGREES},
        {"pitch_degrees": BLOCKOUT_CAMERA_PITCH_MIN_DEGREES},
        {"distance": BLOCKOUT_CAMERA_MAX_DISTANCE},
        {"target_x": BLOCKOUT_CAMERA_TARGET_MAX},
        {"target_y": BLOCKOUT_CAMERA_TARGET_MIN},
        {"target_z": BLOCKOUT_CAMERA_TARGET_MAX},
    ):
        projected = project_blockout_scene(
            update_blockout_camera(endpoint_scene, **camera_update), 8192, 8192
        )
        json.dumps(projected, allow_nan=False)


def test_painter_3d_blockout_panel_updates_scene_and_overlay() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QEvent, QPoint, Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QApplication

    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.painter_3d_blockout import (
        BLOCKOUT_CAMERA_DEFAULT_TARGET,
        BLOCKOUT_CAMERA_MAX_DISTANCE,
        BLOCKOUT_CAMERA_TARGET_MAX,
        BLOCKOUT_CAMERA_TARGET_MIN,
        apply_blockout_camera_preset,
        update_blockout_camera,
    )

    app = QApplication.instance() or QApplication([])
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(640, 360, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.show()
    app.processEvents()

    dialog._set_canvas_workspace_mode("3d_place")
    app.processEvents()
    assert dialog._canvas_workspace_mode == "3d_place"
    assert dialog._blockout_transform_mode == "move"
    assert dialog._blockout_transform_buttons["move"].isChecked()
    assert dialog._paint_3d_blockout_panel.isHidden()
    assert dialog._blockout_canvas_shape_palette.isVisible()

    boundary_camera = update_blockout_camera(
        dialog._current_3d_blockout_scene(),
        target_x=BLOCKOUT_CAMERA_TARGET_MAX,
        target_y=BLOCKOUT_CAMERA_TARGET_MAX,
        target_z=BLOCKOUT_CAMERA_TARGET_MAX,
        distance=BLOCKOUT_CAMERA_MAX_DISTANCE,
    )
    dialog._store_3d_blockout_scene(boundary_camera)
    dialog._nudge_3d_blockout_camera(Qt.Key.Key_W)
    dialog._zoom_3d_blockout_camera(-120)
    bounded_camera = dialog._current_3d_blockout_scene().camera
    assert BLOCKOUT_CAMERA_TARGET_MIN <= bounded_camera.target[0] <= BLOCKOUT_CAMERA_TARGET_MAX
    assert BLOCKOUT_CAMERA_TARGET_MIN <= bounded_camera.target[1] <= BLOCKOUT_CAMERA_TARGET_MAX
    assert BLOCKOUT_CAMERA_TARGET_MIN <= bounded_camera.target[2] <= BLOCKOUT_CAMERA_TARGET_MAX
    assert bounded_camera.distance == BLOCKOUT_CAMERA_MAX_DISTANCE
    dialog._store_3d_blockout_scene(
        update_blockout_camera(
            apply_blockout_camera_preset(
                dialog._current_3d_blockout_scene(), "perspective"
            ),
            target_x=BLOCKOUT_CAMERA_DEFAULT_TARGET[0],
            target_y=BLOCKOUT_CAMERA_DEFAULT_TARGET[1],
            target_z=BLOCKOUT_CAMERA_DEFAULT_TARGET[2],
        )
    )
    assert dialog._blockout_scene_menu_btn.isVisible()
    scene_menu = dialog._build_3d_blockout_scene_menu()
    assert [action.text() for action in scene_menu.actions()] == [
        "Grid",
        "Floor",
        "Lit",
        "Shadows",
        "Fog",
        "Depth",
        "Snap to Grid",
        "Camera",
        "",
        "Duplicate Selected",
        "Place Selected on Ground",
        "Delete Selected",
        "Bake 3D Guide to Paint Layer",
    ]

    dialog.resize(980, 680)
    app.processEvents()
    assert dialog._canvas_workspace_mode == "3d_place"
    assert dialog._canvas_mode_3d_btn.isChecked()
    assert dialog._blockout_canvas_shape_palette.isVisible()
    dialog.showMaximized()
    app.processEvents()
    dialog.showNormal()
    app.processEvents()
    assert dialog._canvas_workspace_mode == "3d_place"
    assert dialog._canvas_mode_3d_btn.isChecked()
    assert dialog._blockout_canvas_shape_palette.isVisible()

    dialog._add_3d_blockout_primitive("box")
    app.processEvents()
    scene = dialog._current_3d_blockout_scene().to_dict()
    assert scene["primitive_count"] == 1
    blockout_layer = dialog._paint_layer_by_id("paint-layer-3d-blockout")
    assert blockout_layer is not None
    assert blockout_layer.opacity == 100
    assert dialog._paint_layers[0].layer_id == "paint-layer-3d-blockout"
    assert dialog._blockout_overlay_label.isVisible()
    renderer = dialog.painter_action_state()["gpu"]["blockout_renderer"]
    assert renderer["active"] in {"opengl", "qpainter"}
    assert renderer["renderer"] in {"painter_blockout_opengl_offscreen_v1", "painter_blockout_qpainter_v1"}
    assert dialog.painter_action_state()["gpu"]["remote_safe"] is True

    dialog._painter_3d_blockout_controls["sx"].setValue(240)
    dialog._painter_3d_blockout_controls["cam_fov"].setValue(36)
    app.processEvents()
    scene = dialog._current_3d_blockout_scene().to_dict()
    assert scene["primitives"][0]["scale"][0] == 2.4
    assert scene["camera"]["fov_degrees"] == 36.0

    bounds = dialog._selected_3d_blockout_bounds(dialog.canvas.width(), dialog.canvas.height())
    assert bounds is not None
    center = bounds.center()
    dialog._set_3d_blockout_transform_mode("move")
    x_axis = dialog._blockout_gizmo_axis_points(bounds)["x"]
    x_axis_start = QPoint(
        int(center.x() + (x_axis.x() - center.x()) * 0.55),
        int(center.y() + (x_axis.y() - center.y()) * 0.55),
    )
    before_axis_move = dialog._current_3d_blockout_scene().to_dict()["primitives"][0]
    assert dialog._begin_3d_blockout_drag(dialog.canvas, x_axis_start)
    assert dialog._blockout_active_axis == "x"
    dialog._update_3d_blockout_drag(
        dialog.canvas,
        QPoint(x_axis_start.x() + 36, x_axis_start.y() + 6),
    )
    dialog._finish_3d_blockout_drag()
    after_axis_move = dialog._current_3d_blockout_scene().to_dict()["primitives"][0]
    assert after_axis_move["position"][0] > before_axis_move["position"][0]
    assert after_axis_move["position"][1:] == before_axis_move["position"][1:]
    assert dialog._blockout_active_axis == ""

    dialog._set_3d_blockout_transform_mode("scale")
    bounds = dialog._selected_3d_blockout_bounds(dialog.canvas.width(), dialog.canvas.height())
    geometry = dialog._blockout_gizmo_geometry(bounds)
    z_center = geometry["center"]
    z_end = geometry["axes"]["z"]
    z_start = QPoint(
        int(z_center.x() + (z_end.x() - z_center.x()) * 0.65),
        int(z_center.y() + (z_end.y() - z_center.y()) * 0.65),
    )
    scale_before = dialog._current_3d_blockout_scene().to_dict()["primitives"][0]
    assert dialog._begin_3d_blockout_drag(dialog.canvas, z_start)
    assert dialog._blockout_active_axis == "z"
    dialog._update_3d_blockout_drag(
        dialog.canvas,
        QPoint(int(z_start.x() + (z_end.x() - z_center.x()) * 0.5), int(z_start.y() + (z_end.y() - z_center.y()) * 0.5)),
    )
    dialog._finish_3d_blockout_drag()
    scale_after = dialog._current_3d_blockout_scene().to_dict()["primitives"][0]
    assert scale_after["scale"][2] > scale_before["scale"][2]
    assert scale_after["scale"][:2] == scale_before["scale"][:2]

    dialog._set_3d_blockout_transform_mode("move")
    bounds = dialog._selected_3d_blockout_bounds(dialog.canvas.width(), dialog.canvas.height())
    assert bounds is not None
    center = bounds.center()
    assert dialog._begin_3d_blockout_drag(dialog.canvas, QPoint(int(center.x()), int(center.y())))
    dialog._update_3d_blockout_drag(dialog.canvas, QPoint(int(center.x() + 40), int(center.y() - 20)))
    dialog._finish_3d_blockout_drag()
    app.processEvents()
    moved = dialog._current_3d_blockout_scene().to_dict()["primitives"][0]
    assert moved["position"][0] > 0.35
    assert moved["position"][2] > 0.65

    dialog._set_3d_blockout_transform_mode("scale")
    bounds = dialog._selected_3d_blockout_bounds(dialog.canvas.width(), dialog.canvas.height())
    assert bounds is not None
    scale_handle = dialog._blockout_scale_handle(bounds)
    assert dialog._begin_3d_blockout_drag(dialog.canvas, QPoint(int(scale_handle.x()), int(scale_handle.y())))
    dialog._update_3d_blockout_drag(
        dialog.canvas,
        QPoint(int(scale_handle.x() + 45), int(scale_handle.y() + 30)),
    )
    dialog._finish_3d_blockout_drag()
    app.processEvents()
    scaled = dialog._current_3d_blockout_scene().to_dict()["primitives"][0]
    assert scaled["scale"][0] > moved["scale"][0]
    assert scaled["scale"][2] > moved["scale"][2]

    bounds = dialog._selected_3d_blockout_bounds(dialog.canvas.width(), dialog.canvas.height())
    assert bounds is not None
    rotate_handle = dialog._blockout_rotate_handle(bounds)
    assert dialog._begin_3d_blockout_drag(dialog.canvas, QPoint(int(rotate_handle.x()), int(rotate_handle.y())))
    dialog._update_3d_blockout_drag(
        dialog.canvas,
        QPoint(int(rotate_handle.x() + 35), int(rotate_handle.y() - 22)),
    )
    dialog._finish_3d_blockout_drag()
    app.processEvents()
    rotated = dialog._current_3d_blockout_scene().to_dict()["primitives"][0]
    assert abs(rotated["rotation"][2]) > 1.0

    camera_before = dialog._current_3d_blockout_scene().camera.target
    dialog.keyPressEvent(
        QKeyEvent(
            QEvent.Type.KeyPress,
            Qt.Key.Key_W,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    camera_after = dialog._current_3d_blockout_scene().camera.target
    assert camera_after != camera_before

    dialog._selected_layer_id = "paint-layer-3d-blockout"
    dialog._on_layer_opacity_changed(55)
    assert dialog._3d_blockout_layer().opacity == 55

    bake = dialog._bake_3d_blockout_to_layer()
    app.processEvents()
    assert bake is not None
    assert bake["stroke_count"] > 0
    assert bake["layer_name"] == "3D Blockout Guide"
    assert dialog._active_paint_layer().name == "3D Blockout Guide"
    assert any(
        str(getattr(stroke, "source_tool", "") or "") == "3d_blockout"
        for stroke in dialog.canvas.embedded_strokes()
    )

    dialog.close()
    dialog.deleteLater()
    app.processEvents()
