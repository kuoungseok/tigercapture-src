from __future__ import annotations

import os
from pathlib import Path


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
    assert "box" in projection["scene"]["supported_primitives"]
    assert "arch" in projection["scene"]["supported_primitives"]

    image = render_blockout_scene_qimage(scene, 320, 180)
    assert image.width() == 320
    assert image.height() == 180
    out = tmp_path / "blockout_preview.png"
    assert image.save(str(out))
    assert out.exists()


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
    assert primitive["color"] == "#7C8CFF"
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
    assert grounded["position"][1] == 0.0

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
    from app.painter_3d_blockout import add_blockout_primitive, default_blockout_scene, update_blockout_camera

    scene = add_blockout_primitive(default_blockout_scene(), kind="box", sx=2.0)
    scene = update_blockout_camera(scene, yaw_degrees=18, pitch_degrees=-8, target_x=0.25, distance=4.5, fov_degrees=33)
    camera = scene.to_dict()["camera"]
    assert camera["yaw_degrees"] == 18.0
    assert camera["pitch_degrees"] == -8.0
    assert camera["target"][0] == 0.25
    assert camera["distance"] == 4.5
    assert camera["fov_degrees"] == 33.0


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

    dialog._add_3d_blockout_primitive("box")
    app.processEvents()
    scene = dialog._current_3d_blockout_scene().to_dict()
    assert scene["primitive_count"] == 1
    assert dialog._blockout_overlay_label.isVisible()

    dialog._painter_3d_blockout_controls["sx"].setValue(240)
    dialog._painter_3d_blockout_controls["cam_fov"].setValue(36)
    app.processEvents()
    scene = dialog._current_3d_blockout_scene().to_dict()
    assert scene["primitives"][0]["scale"][0] == 2.4
    assert scene["camera"]["fov_degrees"] == 36.0

    bounds = dialog._selected_3d_blockout_bounds(dialog.canvas.width(), dialog.canvas.height())
    assert bounds is not None
    center = bounds.center()
    assert dialog._begin_3d_blockout_drag(dialog.canvas, QPoint(int(center.x()), int(center.y())))
    dialog._update_3d_blockout_drag(dialog.canvas, QPoint(int(center.x() + 40), int(center.y() - 20)))
    dialog._finish_3d_blockout_drag()
    app.processEvents()
    moved = dialog._current_3d_blockout_scene().to_dict()["primitives"][0]
    assert moved["position"][0] > 0.35
    assert moved["position"][1] > 0.15

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
    assert scaled["scale"][1] > moved["scale"][1]

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
