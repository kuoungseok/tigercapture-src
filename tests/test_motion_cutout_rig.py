from __future__ import annotations

import pytest
import numpy as np
from PIL import Image, ImageDraw
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication, QDialog

from app.actions.registry import ActionRegistry
from app.motion_designer.cutout_rig import ArmJointLayout, apply_arm_wave_rig
from app.motion_designer.evaluator import evaluate_composition
from app.motion_designer.export_renderer import MotionExportRenderer
from app.motion_designer.schema import MotionComposition, MotionLayer, SourceRef
from app.motion_designer.ui.cutout_rig_dialog import CutoutArmRigDialog


def _composition() -> tuple[MotionComposition, list[MotionLayer]]:
    layers = [
        MotionLayer(id="torso", name="Torso", out_ms=4000),
        MotionLayer(id="upper", name="Upper Arm", out_ms=4000),
        MotionLayer(id="forearm", name="Forearm", out_ms=4000),
        MotionLayer(id="hand", name="Hand", out_ms=4000),
    ]
    for layer in layers:
        layer.source.params.update({"width": 640, "height": 360})
        layer.transform.position.default = [320.0, 180.0]
    return MotionComposition(width=640, height=360, duration_ms=4000, layers=layers), layers


def test_arm_wave_builds_parent_chain_and_propagates_joint_rotation() -> None:
    composition, layers = _composition()
    report = apply_arm_wave_rig(
        composition,
        torso=layers[0],
        upper_arm=layers[1],
        forearm=layers[2],
        hand=layers[3],
        joints=ArmJointLayout(
            shoulder=(380.0, 135.0),
            elbow=(425.0, 185.0),
            wrist=(455.0, 235.0),
        ),
        start_ms=400,
        end_ms=3000,
        side="right",
        cycles=3,
    )

    assert report["schema"] == "tigerstudio.motion.cutout_arm_rig.v1"
    assert layers[1].parent_id == "torso"
    assert layers[2].parent_id == "upper"
    assert layers[3].parent_id == "forearm"
    assert layers[1].transform.anchor.default == pytest.approx([380 / 640, 135 / 360])
    assert layers[2].transform.anchor.default == pytest.approx([425 / 640, 185 / 360])
    assert layers[3].transform.anchor.default == pytest.approx([455 / 640, 235 / 360])

    idle = {row.id: row for row in evaluate_composition(composition, 300)}
    raised = {row.id: row for row in evaluate_composition(composition, 1300)}
    alternate = {row.id: row for row in evaluate_composition(composition, 1700)}
    lowered = {row.id: row for row in evaluate_composition(composition, 3000)}
    assert raised["hand"].matrix != idle["hand"].matrix
    assert alternate["hand"].matrix != raised["hand"].matrix
    assert lowered["upper"].rotation == pytest.approx(0.0)
    assert lowered["forearm"].rotation == pytest.approx(0.0)
    assert lowered["hand"].rotation == pytest.approx(0.0)


def test_arm_wave_action_is_registered_and_mutates_four_layers() -> None:
    class Owner:
        def __init__(self) -> None:
            self._motion_compositions = {}

    registry = ActionRegistry(Owner())
    created = registry.execute(
        "motion.composition.create",
        {"name": "Cutout Arm", "width": 640, "height": 360, "duration_ms": 4000},
    )
    composition_id = created.result["payload"]["composition"]["id"]
    layer_ids: list[str] = []
    for name in ("Torso", "Upper Arm", "Forearm", "Hand"):
        added = registry.execute(
            "motion.layer.add",
            {
                "composition_id": composition_id,
                "layer": {
                    "name": name,
                    "layer_type": "shape",
                    "out_ms": 4000,
                    "source": {"kind": "shape", "params": {"width": 640, "height": 360}},
                },
            },
        )
        rows = added.result["payload"]["composition"]["layers"]
        layer_ids.append(next(row["id"] for row in rows if row["name"] == name))

    result = registry.execute(
        "motion.cutout_rig.arm_wave.create",
        {
            "composition_id": composition_id,
            "torso_layer_id": layer_ids[0],
            "upper_arm_layer_id": layer_ids[1],
            "forearm_layer_id": layer_ids[2],
            "hand_layer_id": layer_ids[3],
            "shoulder": [380, 135],
            "elbow": [425, 185],
            "wrist": [455, 235],
            "start_ms": 400,
            "end_ms": 3000,
            "side": "right",
            "cycles": 3,
        },
    )
    assert result.ok is True
    assert result.result["changed"] is True
    payload = result.result
    assert payload["schema"] == "tigerstudio.motion.cutout_arm_rig.v1"
    assert payload["hand_layer_id"] == layer_ids[3]


def test_arm_wave_dialog_exposes_four_parts_and_commits_editable_rig() -> None:
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    app = QApplication.instance() or QApplication([])
    composition, layers = _composition()
    dialog = CutoutArmRigDialog(composition)
    for index, role in enumerate(("torso", "upper_arm", "forearm", "hand")):
        dialog.layer_boxes[role].setCurrentIndex(index)
    dialog._accept_rig()
    assert dialog.result() == QDialog.Accepted
    result = dialog.result_composition()
    by_id = {layer.id: layer for layer in result.layers}
    assert by_id["upper"].parent_id == "torso"
    assert by_id["forearm"].parent_id == "upper"
    assert by_id["hand"].parent_id == "forearm"
    assert len(by_id["hand"].transform.rotation.keyframes) >= 5
    dialog.close()
    app.processEvents()


def test_arm_wave_moves_rendered_hand_pixels_through_parent_chain(tmp_path) -> None:
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    QApplication.instance() or QApplication([])
    width, height = 320, 240
    drawings = (
        ("torso", "#4d79ff", (115, 70, 205, 225)),
        ("upper", "#36a66a", (190, 80, 218, 145)),
        ("forearm", "#f2c14e", (203, 130, 230, 195)),
        ("hand", "#ef476f", (204, 184, 238, 222)),
    )
    layers: list[MotionLayer] = []
    for name, color, bounds in drawings:
        path = tmp_path / f"{name}.png"
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        ImageDraw.Draw(image).rounded_rectangle(bounds, radius=8, fill=color)
        image.save(path)
        layer = MotionLayer(
            id=name,
            name=name.title(),
            layer_type="image",
            source=SourceRef(
                kind="image",
                uri=str(path),
                params={"width": width, "height": height, "fit": "stretch"},
            ),
            out_ms=3000,
        )
        layer.transform.position.default = [width / 2, height / 2]
        layers.append(layer)
    composition = MotionComposition(
        width=width,
        height=height,
        duration_ms=3000,
        layers=layers,
    )
    apply_arm_wave_rig(
        composition,
        torso=layers[0],
        upper_arm=layers[1],
        forearm=layers[2],
        hand=layers[3],
        joints=ArmJointLayout(
            shoulder=(204, 92),
            elbow=(211, 142),
            wrist=(217, 192),
        ),
        start_ms=250,
        end_ms=2600,
        side="right",
        cycles=2,
    )
    renderer = MotionExportRenderer()
    idle = renderer.render_rgba_array(composition, 100)
    raised = renderer.render_rgba_array(composition, 1250)

    def centroid(frame: np.ndarray) -> tuple[float, float]:
        red = (
            (frame[:, :, 0] > 190)
            & (frame[:, :, 1] < 120)
            & (frame[:, :, 2] < 160)
            & (frame[:, :, 3] > 0)
        )
        ys, xs = np.nonzero(red)
        assert len(xs) > 40
        return float(xs.mean()), float(ys.mean())

    idle_center = centroid(idle)
    raised_center = centroid(raised)
    assert abs(raised_center[0] - idle_center[0]) > 15
    assert abs(raised_center[1] - idle_center[1]) > 15
