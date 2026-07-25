from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace


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
    assert projection["scene"]["primitive_count"] == 3
    assert projection["face_count"] > 0
    assert projection["edge_count"] > 0
    assert projection["scene"]["material_lit"] is True
    assert projection["scene"]["show_shadows"] is True
    assert projection["scene"]["show_floor"] is True
    assert projection["scene"]["light_yaw_degrees"] == 45.0
    assert projection["scene"]["light_pitch_degrees"] == 45.0
    assert projection["shadows"]
    assert projection["floor_tiles"]
    assert {tile["world_tile_size"] for tile in projection["floor_tiles"]} == {1.0}
    assert "box" in projection["scene"]["supported_primitives"]
    assert "arch" in projection["scene"]["supported_primitives"]

    image = render_blockout_scene_qimage(scene, 320, 180)
    assert image.width() == 320
    assert image.height() == 180
    out = tmp_path / "blockout_preview.png"
    assert image.save(str(out))
    assert out.exists()


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
    assert status["surfaces"]["blockout_preview"] == "opengl_offscreen_if_available"


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


def test_painter_3d_blockout_crud_normalizes_and_rejects_duplicate_ids() -> None:
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

    scene = add_blockout_primitive(
        default_blockout_scene(),
        primitive_id="blockout:room",
        kind="unknown",
        color="bad",
        opacity=9.0,
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

    scene = apply_blockout_camera_preset(scene, "top")
    assert scene.to_dict()["camera"]["pitch_degrees"] == -82.0

    scene = delete_blockout_primitive(scene, "blockout:room")
    assert scene.to_dict()["primitive_count"] == 1


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


def test_painter_3d_blockout_panel_updates_scene_and_overlay() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QApplication

    from app.drawing import PaintDialog, create_blank_paint_pixmap

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
    assert dialog._paint_3d_blockout_panel.isHidden()
    assert dialog._blockout_canvas_shape_palette.isVisible()
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
