from pathlib import Path

import pytest

from app.actions.registry import ActionRegistry
from app.motion_designer.relink import apply_motion_relink, build_motion_relink_plan
from app.motion_designer.schema import MotionComposition, MotionLayer, SourceRef


def _composition(root: Path) -> MotionComposition:
    model = root / "actors" / "model.pmx"
    motion = root / "motions" / "dance.vmd"
    font = root / "fonts" / "studio.ttf"
    sprite = root / "particles" / "spark.png"
    actor = MotionLayer(
        name="MMD", layer_type="mmd",
        source=SourceRef(kind="mmd", uri=str(model), params={
            "asset": {"model_path": str(model), "motion_path": str(motion)},
        }),
    )
    text = MotionLayer(
        name="Title", layer_type="text",
        source=SourceRef(kind="text", params={"font_file": str(font)}),
    )
    particles = MotionLayer(
        name="Spark", layer_type="particle",
        source=SourceRef(kind="particle", params={
            "particle": {"shape": "sprite", "sprite_uri": str(sprite)},
        }),
    )
    return MotionComposition(layers=[actor, text, particles])


def _write_tree(root: Path) -> None:
    for relative in (
        "actors/model.pmx", "motions/dance.vmd", "fonts/studio.ttf", "particles/spark.png",
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(relative.encode("ascii"))


def test_relink_moved_project_preserves_relative_structure(tmp_path: Path) -> None:
    old_root = tmp_path / "old"
    new_root = tmp_path / "new"
    _write_tree(old_root)
    composition = _composition(old_root)
    _write_tree(new_root)
    plan = build_motion_relink_plan(composition, old_root=old_root, new_root=new_root)
    assert plan["ok"] is True
    assert plan["changed_count"] == 5
    candidate, result = apply_motion_relink(composition, old_root=old_root, new_root=new_root)
    assert result["changed_count"] == 5
    assert candidate.revision == composition.revision + 1
    assert Path(candidate.layers[0].source.uri) == new_root / "actors" / "model.pmx"
    assert Path(candidate.layers[0].source.params["asset"]["motion_path"]) == new_root / "motions" / "dance.vmd"
    assert Path(candidate.layers[1].source.params["font_file"]) == new_root / "fonts" / "studio.ttf"
    assert Path(candidate.layers[2].source.params["particle"]["sprite_uri"]) == new_root / "particles" / "spark.png"


def test_relink_blocks_ambiguous_basename(tmp_path: Path) -> None:
    old_root = tmp_path / "old"
    outside = tmp_path / "outside" / "clip.png"
    outside.parent.mkdir()
    outside.write_bytes(b"old")
    composition = MotionComposition(layers=[
        MotionLayer(layer_type="image", source=SourceRef(kind="image", uri=str(outside))),
    ])
    new_root = tmp_path / "new"
    for folder in ("a", "b"):
        path = new_root / folder / "clip.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(folder.encode("ascii"))
    plan = build_motion_relink_plan(composition, old_root=old_root, new_root=new_root)
    assert plan["ok"] is False and plan["ambiguous_count"] == 1
    with pytest.raises(ValueError, match="manual review"):
        apply_motion_relink(composition, old_root=old_root, new_root=new_root)


def test_relink_does_not_treat_same_named_directory_as_an_asset(tmp_path: Path) -> None:
    old_root = tmp_path / "old"
    source = old_root / "media" / "plate.png"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"old")
    new_root = tmp_path / "new"
    (new_root / "media" / "plate.png").mkdir(parents=True)
    composition = MotionComposition(layers=[
        MotionLayer(
            name="Plate", layer_type="image",
            source=SourceRef(kind="image", uri=str(source)),
        ),
    ])

    report = build_motion_relink_plan(composition, old_root=old_root, new_root=new_root)

    assert report["resolved_count"] == 0
    assert report["missing_count"] == 1
    assert report["ok"] is False


class _Owner:
    def __init__(self, composition: MotionComposition) -> None:
        self._motion_compositions = {composition.id: composition}


def test_relink_actions_plan_and_apply(tmp_path: Path) -> None:
    old_root = tmp_path / "old"
    new_root = tmp_path / "new"
    _write_tree(old_root)
    _write_tree(new_root)
    composition = _composition(old_root)
    owner = _Owner(composition)
    registry = ActionRegistry(owner)
    params = {"composition_id": composition.id, "old_root": str(old_root), "new_root": str(new_root)}
    plan = registry.execute("motion.source.relink.plan", params)
    applied = registry.execute("motion.source.relink.apply", params)
    assert plan.ok and plan.result["changed_count"] == 5
    assert applied.ok and applied.result["changed_count"] == 5
    assert Path(owner._motion_compositions[composition.id].layers[0].source.uri).is_file()
