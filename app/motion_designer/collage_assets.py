"""Deterministic built-in materials for the Mixed Media Collage workspace."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from .craft_style import make_craft_style_effect
from .schema import MotionComposition, MotionLayer, SourceRef


COLLAGE_ASSET_PACK_CONTRACT = "tigerstudio.motion.collage_asset_pack.v1"

COLLAGE_ASSETS: dict[str, dict[str, Any]] = {
    "cotton_paper": {
        "name": "Cotton Paper",
        "description": "Warm fine-grain paper for titles and product cards.",
        "fill": "#E8DDC3",
        "width_ratio": 0.62,
        "aspect": 1.55,
        "radius": 8,
        "craft_preset": "luxury_paper",
        "craft": {"grain_amount": 0.09, "edge_fiber_amount": 0.22},
    },
    "kraft_cardboard": {
        "name": "Kraft Cardboard",
        "description": "Coarse warm board for cutout panels and packaging.",
        "fill": "#A97745",
        "width_ratio": 0.58,
        "aspect": 1.45,
        "radius": 4,
        "craft_preset": "handmade",
        "craft": {
            "grain_amount": 0.22,
            "grain_size": 3.4,
            "edge_roughness": 0.08,
            "edge_fiber_amount": 0.35,
        },
    },
    "newsprint": {
        "name": "Newsprint",
        "description": "Cool off-white stock for editorial headline layouts.",
        "fill": "#D8D4C8",
        "width_ratio": 0.68,
        "aspect": 1.35,
        "radius": 0,
        "craft_preset": "archive_print",
        "craft": {
            "grain_amount": 0.12,
            "dust_amount": 0.025,
            "misregistration": 0.65,
            "warmth": -0.03,
        },
    },
    "masking_tape": {
        "name": "Masking Tape",
        "description": "Semi-transparent tape strip for pinning collage layers.",
        "fill": "#E7D59B",
        "opacity": 0.72,
        "width_ratio": 0.32,
        "aspect": 5.8,
        "radius": 2,
        "craft_preset": "luxury_paper",
        "craft": {
            "grain_amount": 0.08,
            "edge_roughness": 0.12,
            "edge_fiber_amount": 0.45,
            "edge_fiber_length": 12.0,
        },
    },
    "black_ink": {
        "name": "Black Ink Card",
        "description": "Dense ink surface for labels, masks, and contrast bands.",
        "fill": "#17191D",
        "width_ratio": 0.5,
        "aspect": 2.6,
        "radius": 1,
        "craft_preset": "printed_poster",
        "craft": {
            "grain_amount": 0.07,
            "misregistration": 0.0,
            "edge_roughness": 0.16,
        },
    },
    "graphite": {
        "name": "Graphite Sheet",
        "description": "Neutral textured plate for sketch and annotation layers.",
        "fill": "#777675",
        "width_ratio": 0.54,
        "aspect": 1.65,
        "radius": 3,
        "craft_preset": "rough_cut",
        "craft": {
            "grain_amount": 0.32,
            "grain_chroma": 0.0,
            "scratch_amount": 0.018,
            "warmth": -0.12,
        },
    },
}


def collage_asset_catalog() -> list[dict[str, Any]]:
    return [
        {"id": asset_id, **deepcopy(payload)}
        for asset_id, payload in COLLAGE_ASSETS.items()
    ]


def create_collage_asset_layer(
    composition: MotionComposition,
    asset_id: str,
    *,
    seed: int = 17,
) -> MotionLayer:
    key = str(asset_id or "").strip().lower()
    if key not in COLLAGE_ASSETS:
        raise ValueError(f"unknown collage asset: {asset_id}")
    asset = COLLAGE_ASSETS[key]
    width = max(48.0, composition.width * float(asset["width_ratio"]))
    height = max(24.0, width / float(asset["aspect"]))
    layer = MotionLayer(
        name=str(asset["name"]),
        layer_type="shape",
        source=SourceRef(kind="shape", params={
            "width": width,
            "height": height,
            "fill": str(asset["fill"]),
            "stroke_width": 0,
            "radius": float(asset["radius"]),
        }),
        out_ms=max(1, composition.duration_ms),
        metadata={
            "collage_asset": {
                "schema": COLLAGE_ASSET_PACK_CONTRACT,
                "asset_id": key,
                "procedural": True,
                "seed": max(0, int(seed)),
            },
        },
    )
    layer.transform.position.default = [
        composition.width * 0.5,
        composition.height * 0.5,
    ]
    layer.transform.opacity.default = float(asset.get("opacity", 1.0))
    layer.effects.append(make_craft_style_effect(
        {**dict(asset["craft"]), "seed": max(0, int(seed))},
        preset=str(asset["craft_preset"]),
    ))
    return layer


__all__ = [
    "COLLAGE_ASSET_PACK_CONTRACT",
    "COLLAGE_ASSETS",
    "collage_asset_catalog",
    "create_collage_asset_layer",
]
