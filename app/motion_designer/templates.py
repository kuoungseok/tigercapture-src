"""Built-in Motion Designer templates with stable published controls."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping

from .particles import create_particle_layer
from .schema import MotionBehaviorRef, MotionComposition, MotionLayer, SourceRef, new_motion_id


TEMPLATE_SCHEMA = "tigercapture.motion.template.v1"
TEMPLATE_VARIANTS = {
    "16:9": (1920, 1080),
    "9:16": (1080, 1920),
    "1:1": (1080, 1080),
}


@dataclass(frozen=True, slots=True)
class PublishedControl:
    id: str
    label: str
    value_type: str
    default: Any

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "label": self.label, "value_type": self.value_type, "default": self.default}


@dataclass(frozen=True, slots=True)
class MotionTemplate:
    id: str
    name: str
    category: str
    variants: tuple[str, ...]
    controls: tuple[PublishedControl, ...]
    realtime_grade: str = "realtime"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": TEMPLATE_SCHEMA, "id": self.id, "name": self.name,
            "category": self.category, "variants": list(self.variants),
            "published_controls": [item.to_dict() for item in self.controls],
            "realtime_grade": self.realtime_grade,
        }


COMMON_CONTROLS = (
    PublishedControl("headline", "Headline", "string", "TIGER STUDIO"),
    PublishedControl("subtitle", "Subtitle", "string", "MOTION DESIGN"),
    PublishedControl("accent_color", "Accent", "color", "#43d7b5"),
    PublishedControl("surface_color", "Surface", "color", "#10151c"),
    PublishedControl("duration_ms", "Duration", "integer", 4000),
)


_TEMPLATES = (
    MotionTemplate("clean_lower_third", "Clean Lower Third", "Titles", tuple(TEMPLATE_VARIANTS), COMMON_CONTROLS),
    MotionTemplate("character_nameplate", "Character Nameplate", "Character", tuple(TEMPLATE_VARIANTS), COMMON_CONTROLS),
    MotionTemplate("logo_reveal", "Logo Reveal", "Brand", tuple(TEMPLATE_VARIANTS), COMMON_CONTROLS),
    MotionTemplate("product_callout", "Product Callout", "Commerce", tuple(TEMPLATE_VARIANTS), COMMON_CONTROLS),
    MotionTemplate("stream_stinger", "Stream Stinger", "Broadcast", tuple(TEMPLATE_VARIANTS), COMMON_CONTROLS, "cached"),
    MotionTemplate("music_beat_title", "Music Beat Title", "Music", tuple(TEMPLATE_VARIANTS), COMMON_CONTROLS, "cached"),
    MotionTemplate("vertical_shorts_hook", "Vertical Shorts Hook", "Shorts", ("9:16", "1:1"), COMMON_CONTROLS),
    MotionTemplate("anime_character_intro", "Anime Character Intro", "Character", tuple(TEMPLATE_VARIANTS), COMMON_CONTROLS),
    MotionTemplate("mmd_dance_title", "MMD Dance Title", "Character", tuple(TEMPLATE_VARIANTS), COMMON_CONTROLS),
    MotionTemplate("vrm_stream_starting_ending", "VRM Stream Starting / Ending", "Broadcast", tuple(TEMPLATE_VARIANTS), COMMON_CONTROLS),
)
TEMPLATE_CATALOG = {item.id: item for item in _TEMPLATES}


def list_templates() -> list[dict[str, Any]]:
    return [item.to_dict() for item in _TEMPLATES]


def get_template(template_id: str) -> MotionTemplate:
    try:
        return TEMPLATE_CATALOG[str(template_id)]
    except KeyError as exc:
        raise ValueError(f"unknown Motion template: {template_id}") from exc


def recommended_variant(width: int, height: int) -> str:
    ratio = float(width) / max(1.0, float(height))
    if ratio < .8:
        return "9:16"
    if ratio < 1.25:
        return "1:1"
    return "16:9"


def _controls(template: MotionTemplate, values: Mapping[str, Any] | None) -> dict[str, Any]:
    incoming = dict(values or {})
    known = {item.id for item in template.controls}
    unknown = sorted(set(incoming) - known)
    if unknown:
        raise ValueError(f"unknown published template control: {unknown[0]}")
    result = {item.id: deepcopy(incoming.get(item.id, item.default)) for item in template.controls}
    result["duration_ms"] = max(250, min(600000, int(result["duration_ms"])))
    for key in ("headline", "subtitle", "accent_color", "surface_color"):
        result[key] = str(result[key])
    return result


def _behavior(kind: str, duration: int, **params: Any) -> MotionBehaviorRef:
    return MotionBehaviorRef(kind=kind, start_ms=0, end_ms=max(1, min(duration, 700)), params=params)


def _shape(name: str, width: float, height: float, x: float, y: float, color: str,
           duration: int, *, shape: str = "rectangle", role: str = "shape") -> MotionLayer:
    layer = MotionLayer(
        name=name, layer_type="shape", out_ms=duration,
        source=SourceRef(kind="shape", params={
            "shape": shape, "width": width, "height": height, "fill": color,
            "stroke": "#00000000", "stroke_width": 0,
        }),
        metadata={"template_role": role},
    )
    layer.transform.position.default = [x, y]
    return layer


def _text(name: str, text: str, x: float, y: float, size: float, color: str,
          duration: int, *, role: str, align: str = "left") -> MotionLayer:
    layer = MotionLayer(
        name=name, layer_type="text", out_ms=duration,
        source=SourceRef(kind="typography", params={
            "text": text, "font_family": "Segoe UI", "font_size": size,
            "font_weight": 700 if role == "headline" else 500, "fill": color,
            "align": align, "width": max(320.0, size * max(8, len(text)) * .7), "height": size * 1.8,
            "text_animation": {"in": "slide-up-in", "hold": "none", "out": "fade-out",
                               "unit": "word", "stagger_ms": 45, "in_duration_ms": 450,
                               "out_duration_ms": 350},
        }),
        metadata={"template_role": role},
    )
    layer.transform.position.default = [x, y]
    layer.behaviors.append(_behavior("fade", duration, direction="in", hold_after=True))
    return layer


def _build_layers(template_id: str, width: int, height: int, controls: Mapping[str, Any]) -> list[MotionLayer]:
    duration = int(controls["duration_ms"])
    headline, subtitle = controls["headline"], controls["subtitle"]
    accent, surface = controls["accent_color"], controls["surface_color"]
    landscape = width >= height
    safe_x, safe_y = width * .07, height * .08
    title_size = max(42.0, min(width, height) * (.09 if landscape else .075))
    layers: list[MotionLayer] = []
    if template_id in {"clean_lower_third", "character_nameplate"}:
        plate_width, plate_height = width * (.62 if landscape else .84), height * .19
        x, y = safe_x + plate_width * .5, height - safe_y - plate_height * .5
        plate = _shape("Plate", plate_width, plate_height, x, y, surface, duration, role="surface")
        plate.behaviors.append(_behavior("slide", duration, direction="in", distance=[-width * .12, 0], hold_after=True))
        layers.extend([
            plate,
            _shape("Accent", max(8, width * .009), plate_height, x - plate_width * .5, y, accent, duration, role="accent"),
            _text("Headline", headline, x - plate_width * .4, y - plate_height * .14, title_size * .55, "#ffffff", duration, role="headline"),
            _text("Subtitle", subtitle, x - plate_width * .4, y + plate_height * .22, title_size * .26, "#b8c1cc", duration, role="subtitle"),
        ])
    elif template_id in {"logo_reveal", "music_beat_title"}:
        center = (width * .5, height * .5)
        ring = _shape("Reveal Mark", min(width, height) * .3, min(width, height) * .3,
                      *center, accent, duration, shape="ellipse", role="accent")
        ring.behaviors.append(_behavior("pop", duration, **{"from": .2, "overshoot": .18, "hold_after": True}))
        layers.extend([
            ring,
            _text("Headline", headline, width * .5, height * .48, title_size, "#ffffff", duration,
                  role="headline", align="center"),
            _text("Subtitle", subtitle, width * .5, height * .62, title_size * .32, "#d9e0e7", duration,
                  role="subtitle", align="center"),
        ])
    elif template_id == "stream_stinger":
        wipe = _shape("Stinger Wipe", width * 1.4, height * 1.4, width * .5, height * .5, accent, duration, role="surface")
        wipe.behaviors.append(_behavior("slide", duration, direction="out", distance=[width * 1.3, 0], hold_before=True))
        particles = create_particle_layer(width=width, height=height, duration_ms=duration, params={
            "seed": 8217, "birth_rate": 30, "bursts": [{"time_ms": 100, "count": 50}],
            "particle": {"shape": "triangle", "size_start": 24, "size_end": 4,
                         "opacity_start": 1, "opacity_end": 0, "color_start": accent,
                         "color_end": f"{accent[:7]}00", "rotation_speed": 120, "sprite_uri": ""},
        })
        particles.name = "Stinger Particles"
        particles.metadata["template_role"] = "particles"
        particles.blend_mode = "screen"
        layers.extend([wipe, particles, _text("Headline", headline, width * .5, height * .5, title_size,
                                              "#ffffff", duration, role="headline", align="center")])
    elif template_id == "product_callout":
        card_width, card_height = width * (.38 if landscape else .78), height * .52
        x, y = width - safe_x - card_width * .5, height * .5
        plate = _shape("Callout", card_width, card_height, x, y, surface, duration, role="surface")
        plate.behaviors.append(_behavior("slide", duration, direction="in", distance=[width * .15, 0], hold_after=True))
        layers.extend([
            plate,
            _shape("Product Window", card_width * .78, card_height * .42, x, y - card_height * .18,
                   "#26313c", duration, role="media_slot"),
            _text("Headline", headline, x - card_width * .39, y + card_height * .15, title_size * .52,
                  "#ffffff", duration, role="headline"),
            _text("Subtitle", subtitle, x - card_width * .39, y + card_height * .31, title_size * .28,
                  accent, duration, role="subtitle"),
        ])
    else:
        vertical = template_id == "vertical_shorts_hook"
        x = width * (.5 if vertical else .12)
        align = "center" if vertical else "left"
        title_y = height * (.22 if vertical else .42)
        accent_band = _shape("Accent Band", width * (.72 if vertical else .54), max(10, height * .018),
                             width * .5 if vertical else width * .32, title_y - title_size * .9,
                             accent, duration, role="accent")
        accent_band.behaviors.append(_behavior("scale", duration, **{"from": .05, "hold_after": True}))
        layers.extend([
            accent_band,
            _text("Headline", headline, x, title_y, title_size, "#ffffff", duration, role="headline", align=align),
            _text("Subtitle", subtitle, x, title_y + title_size * 1.15, title_size * .34,
                  "#bac5cf", duration, role="subtitle", align=align),
        ])
        if template_id in {"anime_character_intro", "mmd_dance_title", "vrm_stream_starting_ending"}:
            slot_width = width * (.36 if landscape else .68)
            slot_height = height * (.68 if landscape else .42)
            slot_x = width * (.72 if landscape else .5)
            slot_y = height * (.53 if landscape else .7)
            slot = _shape("Character Slot", slot_width, slot_height, slot_x, slot_y, "#26313c99",
                          duration, role="character_slot")
            slot.behaviors.append(_behavior("pop", duration, **{"from": .9, "overshoot": .06, "hold_after": True}))
            layers.insert(0, slot)
    return layers


def apply_template_to_composition(composition: MotionComposition, template_id: str, *,
                                  variant: str = "", controls: Mapping[str, Any] | None = None) -> MotionComposition:
    template = get_template(template_id)
    chosen_variant = str(variant or recommended_variant(composition.width, composition.height))
    if chosen_variant not in template.variants:
        raise ValueError(f"template {template.id} does not support variant {chosen_variant}")
    values = _controls(template, controls)
    candidate = MotionComposition.from_dict(composition.to_dict())
    layers = _build_layers(template.id, candidate.width, candidate.height, values)
    instance_id = new_motion_id("template_instance")
    for layer in layers:
        layer.id = new_motion_id("layer")
        layer.metadata.update({
            "template_id": template.id,
            "template_instance_id": instance_id,
            "template_variant": chosen_variant,
        })
    candidate.layers.extend(layers)
    candidate.metadata["last_applied_template"] = {
        "schema": TEMPLATE_SCHEMA, "template_id": template.id,
        "template_instance_id": instance_id, "variant": chosen_variant,
        "published_controls": deepcopy(values), "realtime_grade": template.realtime_grade,
    }
    candidate.revision += 1
    return candidate


def instantiate_template(template_id: str, *, variant: str = "16:9",
                         controls: Mapping[str, Any] | None = None) -> MotionComposition:
    template = get_template(template_id)
    if variant not in template.variants:
        raise ValueError(f"template {template.id} does not support variant {variant}")
    width, height = TEMPLATE_VARIANTS[variant]
    values = _controls(template, controls)
    composition = MotionComposition(name=template.name, width=width, height=height,
                                    duration_ms=int(values["duration_ms"]))
    result = apply_template_to_composition(composition, template.id, variant=variant, controls=values)
    result.revision = 1
    return result


def template_cost(template_id: str, *, variant: str = "16:9",
                  controls: Mapping[str, Any] | None = None) -> dict[str, Any]:
    composition = instantiate_template(template_id, variant=variant, controls=controls)
    particle_limit = sum(int(layer.source.params.get("max_particles", 0) or 0)
                         for layer in composition.layers if layer.layer_type == "particle")
    grade = get_template(template_id).realtime_grade
    return {
        "realtime_grade": grade,
        "layer_count": len(composition.layers),
        "particle_limit": particle_limit,
        "requires_pre_render": grade != "realtime",
        "estimated_cost_units": len(composition.layers) + particle_limit / 500.0,
    }


__all__ = [
    "COMMON_CONTROLS", "MotionTemplate", "PublishedControl", "TEMPLATE_CATALOG",
    "TEMPLATE_SCHEMA", "TEMPLATE_VARIANTS", "apply_template_to_composition", "get_template",
    "instantiate_template", "list_templates", "recommended_variant", "template_cost",
]
