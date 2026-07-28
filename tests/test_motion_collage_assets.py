from __future__ import annotations

from app.actions.registry import ActionRegistry
from app.motion_designer.collage_assets import (
    COLLAGE_ASSET_PACK_CONTRACT,
    collage_asset_catalog,
    create_collage_asset_layer,
)
from app.motion_designer.schema import MotionComposition


class _Owner:
    def __init__(self) -> None:
        self._motion_compositions = {}


def test_collage_asset_catalog_creates_editable_procedural_layers() -> None:
    composition = MotionComposition(
        width=1920,
        height=1080,
        duration_ms=5000,
    )
    catalog = collage_asset_catalog()
    assert [row["id"] for row in catalog] == [
        "cotton_paper",
        "kraft_cardboard",
        "newsprint",
        "masking_tape",
        "black_ink",
        "graphite",
    ]
    layers = [
        create_collage_asset_layer(composition, row["id"], seed=42)
        for row in catalog
    ]
    assert all(layer.source.kind == "shape" for layer in layers)
    assert all(layer.effects[0].kind == "craft_style" for layer in layers)
    assert all(
        layer.metadata["collage_asset"]["schema"]
        == COLLAGE_ASSET_PACK_CONTRACT
        for layer in layers
    )
    assert len({layer.source.params["fill"] for layer in layers}) == 6


def test_collage_asset_actions_share_catalog_and_layer_contract() -> None:
    owner = _Owner()
    registry = ActionRegistry(owner)
    created = registry.execute(
        "motion.composition.create",
        {"name": "Mixed Media"},
    )
    composition_id = created.result["payload"]["composition"]["id"]
    catalog = registry.execute("motion.collage.asset.catalog", {})
    assert catalog.ok and catalog.result["count"] == 6
    added = registry.execute("motion.collage.asset.add", {
        "composition_id": composition_id,
        "asset_id": "masking_tape",
        "seed": 88,
    })
    assert added.ok
    assert added.result["layer"]["metadata"]["collage_asset"] == {
        "schema": COLLAGE_ASSET_PACK_CONTRACT,
        "asset_id": "masking_tape",
        "procedural": True,
        "seed": 88,
    }
    assert (
        owner._motion_compositions[composition_id].layers[0].effects[0].kind
        == "craft_style"
    )
