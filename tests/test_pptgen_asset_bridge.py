from __future__ import annotations

from app.pptgen.asset_bridge import asset_kind_for_path, slide_element_from_media_asset, slide_element_from_typography
from app.typography import TextClip, TextStyle


def test_asset_bridge_classifies_editor_assets():
    assert asset_kind_for_path("clip.mp4") == "video_actor"
    assert asset_kind_for_path("scene.gltf") == "ar_pbr_actor"
    assert asset_kind_for_path("model.pmx") == "mmd_actor"
    assert asset_kind_for_path("avatar.vrm") == "vrm_actor"
    assert asset_kind_for_path("still.png") == "image"


def test_media_asset_becomes_editable_ppt_actor():
    element = slide_element_from_media_asset("scene.gltf", "asset-1", x=0.2, y=0.3)

    assert element.kind == "ar_pbr_actor"
    assert element.source_path == "scene.gltf"
    assert element.metadata["editable_actor"] is True
    assert element.metadata["source"] == "media_pool"


def test_typography_clip_becomes_ppt_typography_actor():
    clip = TextClip(text="Hello PPT", style=TextStyle(font_size=48, color="#FF3366", alignment="right"))

    element = slide_element_from_typography(clip, "typo-1")

    assert element.kind == "typography_actor"
    assert element.text == "Hello PPT"
    assert element.style.font_size == 48
    assert element.style.color == "#FF3366"
    assert element.style.align == "right"
