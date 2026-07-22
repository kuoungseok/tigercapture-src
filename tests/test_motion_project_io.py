from app.motion_designer.project_io import inject_motion_document, load_motion_document
from app.motion_designer.schema import MotionComposition


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
