import json

import pytest

from app.actions.registry import ActionRegistry
from app.motion_designer.project_io import (
    MOTION_PROJECT_SCHEMA,
    inject_motion_document,
    load_motion_document,
    load_motion_project,
    save_motion_project,
)
from app.motion_designer.schema import MotionComposition, MotionLayer


def test_old_project_migrates_to_empty_motion_store() -> None:
    loaded = load_motion_document({"version": "1.1"})
    assert loaded.compositions == []
    assert loaded.issues == []


def test_save_load_save_is_canonical_and_one_bad_composition_isolated() -> None:
    composition = MotionComposition(name="Good")
    first = inject_motion_document({"future_root": 7}, [composition])
    first["motion_compositions"].append({"width": 0, "height": 0})
    loaded = load_motion_document(first)
    second = inject_motion_document({"future_root": first["future_root"]}, loaded.compositions)
    assert len(loaded.compositions) == 1
    assert loaded.issues
    assert second["motion_compositions"] == [composition.to_dict()]
    assert second["future_root"] == 7


def test_independent_motion_project_round_trips_atomically(tmp_path) -> None:
    composition = MotionComposition(
        name="Independent Motion",
        layers=[MotionLayer(name="Editable Layer")],
    )
    path = save_motion_project(composition, tmp_path / "lesson")
    assert path.suffix == ".tgmotion"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema"] == MOTION_PROJECT_SCHEMA
    assert payload["format_version"] == 1
    assert not list(tmp_path.glob("*.tmp"))

    loaded = load_motion_project(path)
    assert loaded.to_dict() == composition.to_dict()


def test_independent_motion_project_rejects_foreign_or_invalid_documents(tmp_path) -> None:
    foreign = tmp_path / "foreign.tgmotion"
    foreign.write_text('{"schema":"other"}', encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported Tiger Studio Motion project"):
        load_motion_project(foreign)

    invalid = tmp_path / "invalid.tgmotion"
    invalid.write_text(json.dumps({
        "schema": MOTION_PROJECT_SCHEMA,
        "format_version": 1,
        "composition": {"width": 0, "height": 0},
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid Motion project"):
        load_motion_project(invalid)


def test_independent_motion_project_actions_save_and_load(tmp_path) -> None:
    class Owner:
        def __init__(self) -> None:
            self._motion_compositions = {}
            self._motion_clips = []

    source = Owner()
    composition = MotionComposition(name="Action Document")
    source._motion_compositions[composition.id] = composition
    path = tmp_path / "action_document.tgmotion"
    saved = ActionRegistry(source).execute(
        "motion.project.save",
        {"composition_id": composition.id, "path": str(path)},
    )
    assert saved.ok and path.is_file()

    target = Owner()
    loaded = ActionRegistry(target).execute(
        "motion.project.load",
        {"path": str(path)},
    )
    assert loaded.ok
    assert target._motion_compositions[composition.id].name == "Action Document"
