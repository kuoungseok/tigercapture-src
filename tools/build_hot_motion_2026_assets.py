"""Split generated trend atlases into durable Motion template plates."""
from __future__ import annotations

from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = ROOT / "resources" / "motion_templates" / "hot_2026"


def _save_crop(source: Path, box: tuple[int, int, int, int], name: str) -> Path:
    with Image.open(source) as loaded:
        image = loaded.convert("RGB").crop(box)
    width, height = image.size
    target_height = round(width * 9 / 16)
    if target_height < height:
        top = (height - target_height) // 2
        image = image.crop((0, top, width, top + target_height))
    output = ASSET_ROOT / name
    image.save(output, quality=95)
    return output


def build() -> list[Path]:
    atlas_01 = ASSET_ROOT / "atlas_01.png"
    atlas_02 = ASSET_ROOT / "atlas_02.png"
    atlas_03 = ASSET_ROOT / "atlas_03.png"
    outputs = [
        _save_crop(atlas_01, (0, 0, 834, 469), "prompt_playground.png"),
        _save_crop(atlas_01, (838, 0, 1672, 469), "reality_warp.png"),
        _save_crop(atlas_01, (0, 473, 834, 941), "explorecore.png"),
        _save_crop(atlas_01, (838, 473, 1672, 941), "texture_check.png"),
        _save_crop(atlas_02, (0, 0, 622, 622), "notes_app_chic.png"),
        _save_crop(atlas_02, (630, 0, 1252, 622), "opt_out_era.png"),
        _save_crop(atlas_02, (0, 630, 622, 1252), "drama_club.png"),
        _save_crop(atlas_02, (630, 630, 1252, 1252), "local_craft.png"),
        _save_crop(atlas_03, (0, 0, 508, 1536), "variable_kinetic_type.png"),
        _save_crop(atlas_03, (516, 0, 1024, 1536), "liquid_glass_next.png"),
    ]
    return outputs


if __name__ == "__main__":
    for path in build():
        print(path)
