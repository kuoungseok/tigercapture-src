import sys; sys.path.insert(0, ".")
from app.spine_editor.spine_json_parser import load_spine_file, load_atlas, load_atlas_pages, atlas_is_pma
from app.spine_editor.spine_renderer import SpineRenderer
from PIL import Image
import os
path = "resources/spine_samples/blue_archive/aris_spr/aris_spr.skel"
skel = load_spine_file(path)
print("Skins:", list(skel.skins.keys()))
atlas = load_atlas(path.replace(".skel", ".atlas"))
pages = load_atlas_pages(path.replace(".skel", ".atlas"))
pma = atlas_is_pma(path.replace(".skel", ".atlas"))
base = os.path.dirname(path)
textures = [Image.open(os.path.join(base,pg)).convert("RGBA") for pg in pages]
renderer = SpineRenderer(skel, atlas, textures, pma=pma)
img = renderer.render(512, 768, scale=1.2, anim_name=None, time=0.0, offset_y=250)
img.save("test_ba.png")
print("Saved test_ba.png")
