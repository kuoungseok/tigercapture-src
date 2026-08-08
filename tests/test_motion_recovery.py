from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from app.actions.registry import ActionRegistry
from app.motion_designer.recovery import (
    list_motion_recoveries, motion_recovery_path, read_motion_recovery,
    write_motion_recovery,
)
from app.motion_designer.schema import MotionComposition, MotionLayer
from app.motion_designer.ui.window import MotionDocumentController


def test_atomic_recovery_roundtrip_and_damage_rejection(tmp_path: Path) -> None:
    composition = MotionComposition(name="Recover Me", layers=[MotionLayer(name="Layer")])
    path = motion_recovery_path(tmp_path, composition.id)
    written = write_motion_recovery(composition, path, project_path=tmp_path / "project.tgp")
    recovered, report = read_motion_recovery(path, expected_composition_id=composition.id)
    assert written["checksum_sha256"] == report["checksum_sha256"]
    assert recovered.to_dict() == composition.to_dict()
    assert not list(tmp_path.glob("*.tmp"))

    data = json.loads(path.read_text(encoding="utf-8"))
    data["composition"]["name"] = "Tampered"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="checksum mismatch"):
        read_motion_recovery(path, expected_composition_id=composition.id)
    listed = list_motion_recoveries(tmp_path)
    assert listed["count"] == 1 and listed["recoveries"][0]["valid"] is False


def test_recovery_rejects_other_and_stale_compositions(tmp_path: Path) -> None:
    composition = MotionComposition(revision=4)
    path = motion_recovery_path(tmp_path, composition.id)
    write_motion_recovery(composition, path)
    with pytest.raises(ValueError, match="another composition"):
        read_motion_recovery(path, expected_composition_id="different")
    with pytest.raises(ValueError, match="not newer"):
        read_motion_recovery(path, expected_composition_id=composition.id, current_revision=4)
    recovered, report = read_motion_recovery(
        path, expected_composition_id=composition.id, current_revision=4, allow_stale=True,
    )
    assert recovered.id == composition.id and report["stale"] is True


def test_document_controller_500_edits_undo_redo_roundtrip() -> None:
    changes: list[dict] = []
    composition = MotionComposition(layers=[MotionLayer(name="Editable")])
    layer_id = composition.layers[0].id
    controller = MotionDocumentController(composition, lambda item: changes.append(item.to_dict()))
    for index in range(500):
        controller.update_layer(layer_id, {"name": f"Layer {index}"})
    assert controller.composition.layers[0].name == "Layer 499"
    for _ in range(500):
        controller.undo()
    assert controller.composition.to_dict() == composition.to_dict()
    for _ in range(500):
        controller.redo()
    assert controller.composition.layers[0].name == "Layer 499"
    assert len(changes) == 1500


class _Owner:
    def __init__(self, composition: MotionComposition) -> None:
        self._motion_compositions = {composition.id: composition}


def test_recovery_actions_write_list_and_apply(tmp_path: Path) -> None:
    current = MotionComposition(name="Current", revision=2)
    recovered = MotionComposition.from_dict(current.to_dict())
    recovered.name = "Recovered"
    recovered.revision = 3
    path = motion_recovery_path(tmp_path, recovered.id)
    write_motion_recovery(recovered, path)
    owner = _Owner(current)
    registry = ActionRegistry(owner)
    listed = registry.execute("motion.recovery.list", {"recovery_root": str(tmp_path)})
    applied = registry.execute("motion.recovery.apply", {
        "composition_id": current.id, "path": str(path),
    })
    assert listed.ok and listed.result["count"] == 1
    assert applied.ok and owner._motion_compositions[current.id].name == "Recovered"
    rewrite = registry.execute("motion.recovery.write", {
        "composition_id": current.id, "recovery_root": str(tmp_path),
    })
    assert rewrite.ok and Path(rewrite.result["path"]).is_file()
