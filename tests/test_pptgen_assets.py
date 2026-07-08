from __future__ import annotations


def test_deck_media_pool_add_list_insert_remove(tmp_path):
    from app.pptgen.assets import add_deck_asset, insert_deck_asset_to_slide, list_deck_assets, remove_deck_asset
    from app.pptgen.schema import DeckSpec, SlideSpec

    image = tmp_path / "hero.png"
    image.write_bytes(b"png")
    deck = DeckSpec(id="deck", title="Media Pool")
    slide = SlideSpec(id="slide-001", title="Slide")
    deck.slides.append(slide)

    asset = add_deck_asset(deck, image)
    duplicate = add_deck_asset(deck, image)

    assert asset["id"] == duplicate["id"]
    assert asset["kind"] == "image"
    assets = list_deck_assets(deck)
    assert len(assets) == 1
    assert assets[0]["exists"] is True

    element = insert_deck_asset_to_slide(deck, asset["id"], slide, element_id="el-asset")

    assert element.kind == "image"
    assert element.metadata["ppt_asset_id"] == asset["id"]
    assert slide.elements[0].id == "el-asset"

    removed = remove_deck_asset(deck, asset["id"])
    assert removed["id"] == asset["id"]
    assert list_deck_assets(deck) == []


def test_deck_media_pool_preserves_missing_3d_asset(tmp_path):
    from app.pptgen.assets import add_deck_asset, element_from_deck_asset, list_deck_assets
    from app.pptgen.schema import DeckSpec

    deck = DeckSpec(id="deck")
    model = tmp_path / "scene.gltf"

    asset = add_deck_asset(deck, model, name="Scene")
    listed = list_deck_assets(deck)[0]
    element = element_from_deck_asset(deck, asset["id"], "el-scene")

    assert listed["exists"] is False
    assert listed["kind"] == "ar_pbr_actor"
    assert element.kind == "ar_pbr_actor"
    assert element.name == "Scene"
