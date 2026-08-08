"""Product-ready 2026 trend templates built from editable Motion primitives."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .craft_style import make_craft_style_effect
from .glass_material import make_glass_effect
from .hot_trend_templates import (
    build_hot_trend_template_layers,
    is_hot_trend_template,
)
from .painterly_look import make_painterly_look_effect
from .schema import (
    AnimatedProperty,
    Keyframe,
    MotionBehaviorRef,
    MotionComposition,
    MotionLayer,
    SourceRef,
    new_motion_id,
)
from .stop_motion import set_stop_motion, set_stop_motion_material
from .story_direction import add_story_beat, update_story


TREND_TEMPLATE_SCHEMA = "tigerstudio.motion.trend_template.v1"
TREND_TEMPLATE_STATE_KEY = "trend_template_state"

TREND_TEMPLATE_SPECS: tuple[dict[str, Any], ...] = (
    {
        "id": "luxury_craft_product_reveal",
        "name": "Luxury Craft Product Reveal",
        "category": "2026 Trends",
        "variants": ("16:9", "9:16"),
        "duration_ms": 12000,
        "cta": "DISCOVER THE CRAFT",
        "description": "Tactile paper, restrained grain, product framing, and a premium three-beat reveal.",
        "features": ("Craft Style", "Paper surface", "Product media slots", "Three-beat reveal"),
        "workflow": "Luxury product launch and brand film",
        "replace_items": ("Product images", "Material detail", "Headline", "CTA"),
        "tags": ("craft", "luxury", "paper", "product", "2026"),
        "style": "craft",
        "scenes": (
            ("ORIGIN", "Made with intention", "Begin with material and provenance."),
            ("DETAIL", "Every surface matters", "Reveal one tactile product detail."),
            ("OBJECT", "Designed to be kept", "Resolve on the product and invitation."),
        ),
    },
    {
        "id": "editorial_mixed_media_collage",
        "name": "Editorial Mixed Media Collage",
        "category": "2026 Trends",
        "variants": ("16:9", "9:16", "1:1"),
        "duration_ms": 12000,
        "cta": "READ THE STORY",
        "description": "Layered editorial cards, print offsets, paper shadows, and energetic collage timing.",
        "features": ("Mixed media", "Editable collage cards", "Print misregistration", "Cut-paper motion"),
        "workflow": "Editorial opener, culture promo, and social campaign",
        "replace_items": ("Three photos", "Pull quote", "Issue title", "CTA"),
        "tags": ("collage", "editorial", "print", "mixed media", "2026"),
        "style": "collage",
        "scenes": (
            ("ISSUE 01", "Ideas in motion", "Lead with a cropped image and oversized type."),
            ("CUT / PASTE", "Context becomes texture", "Stack evidence, labels, and a pull quote."),
            ("NEW EDITION", "Make the page move", "Land on the issue cover and CTA."),
        ),
    },
    {
        "id": "liquid_glass_app_promo",
        "name": "Liquid Glass App Promo",
        "category": "2026 Trends",
        "variants": ("16:9", "9:16"),
        "duration_ms": 12000,
        "cta": "OPEN THE APP",
        "description": "Backdrop-aware translucent cards introduce an app without flattening the UI into video.",
        "features": ("Tiger Glass", "Backdrop sampling", "Glossy CTA", "App media slots"),
        "workflow": "App launch, UI feature tour, and product demo",
        "replace_items": ("App screens", "Feature copy", "Brand colors", "CTA"),
        "tags": ("glass", "ui", "app", "product", "2026"),
        "style": "glass",
        "scenes": (
            ("FOCUS", "Your day, clarified", "A clear card rises over live content."),
            ("FLOW", "Everything stays in context", "Layer controls without hiding the backdrop."),
            ("READY", "One touch from done", "Finish on a glossy action surface."),
        ),
    },
    {
        "id": "clay_stop_motion_mascot",
        "name": "Clay Stop-motion Mascot",
        "category": "2026 Trends",
        "variants": ("16:9", "9:16", "1:1"),
        "duration_ms": 10000,
        "cta": "MEET THE CREW",
        "description": "A stepped two-frame mascot spot with clay boil, contact settle, and handmade surfaces.",
        "features": ("Stop-motion timing", "Clay material", "Mascot slot", "On-twos exposure"),
        "workflow": "Mascot bumper, family campaign, and playful ident",
        "replace_items": ("Mascot artwork", "Props", "Tagline", "CTA"),
        "tags": ("stop motion", "clay", "mascot", "craft", "2026"),
        "style": "stop_motion",
        "scenes": (
            ("HELLO", "A little character", "Introduce the mascot with a tactile pop."),
            ("TRY", "A very big idea", "Use stepped motion and a physical-looking prop."),
            ("TOGETHER", "Made to move you", "Settle into the final brand pose."),
        ),
    },
    {
        "id": "emotional_brand_story",
        "name": "Emotional Brand Story",
        "category": "2026 Trends",
        "variants": ("16:9", "9:16"),
        "duration_ms": 15000,
        "cta": "BEGIN YOUR STORY",
        "description": "A human-scale Hook, Conflict, Reveal, Proof, and CTA arc with editable story beats.",
        "features": ("Story Direction", "Five-scene arc", "Character media slots", "Audio cue metadata"),
        "workflow": "Purpose campaign, founder story, and emotional brand film",
        "replace_items": ("Character footage", "Story copy", "Proof", "Music cue", "CTA"),
        "tags": ("story", "brand", "emotion", "character", "2026"),
        "style": "story",
        "scenes": (
            ("A MOMENT", "Every change starts small", "Open on a recognizable human need."),
            ("THE DISTANCE", "Some days ask more of us", "Let tension and space build."),
            ("THE TURN", "Then someone reaches back", "Reveal the action that changes the direction."),
            ("THE PROOF", "Progress becomes visible", "Ground the emotion in one real result."),
            ("TOGETHER", "The next chapter is ours", "Resolve with a held invitation."),
        ),
    },
    {
        "id": "vhs_nostalgia_music_promo",
        "name": "VHS Nostalgia Music Promo",
        "category": "2026 Trends",
        "variants": ("16:9", "9:16", "1:1"),
        "duration_ms": 12000,
        "cta": "LISTEN NOW",
        "description": "Warm analog color, scan wobble, date stamps, and rhythmic media cuts for a music release.",
        "features": ("VHS craft preset", "Music promo cards", "Analog date stamp", "Beat-ready cuts"),
        "workflow": "Single release, live session, and nostalgia campaign",
        "replace_items": ("Artist footage", "Cover art", "Release date", "Track title"),
        "tags": ("vhs", "music", "nostalgia", "analog", "2026"),
        "style": "vhs",
        "scenes": (
            ("PLAY 00:01", "We kept the first take", "Open with a raw performance fragment."),
            ("SIDE A", "Noise becomes memory", "Cut between cover art and handheld footage."),
            ("OUT NOW", "Press play again", "Hold the title, date, and listening CTA."),
        ),
    },
    {
        "id": "kinetic_type_vertical_short",
        "name": "Kinetic Type Vertical Short",
        "category": "2026 Trends",
        "variants": ("9:16", "1:1"),
        "duration_ms": 10000,
        "cta": "MAKE IT MOVE",
        "description": "Fast word-level typography, scale accents, and platform-safe vertical composition.",
        "features": ("Kinetic typography", "Word stagger", "Vertical safe zones", "Rhythmic scale"),
        "workflow": "Shorts hook, lyric card, and creator announcement",
        "replace_items": ("Hook", "Three key phrases", "Brand word", "CTA"),
        "tags": ("kinetic type", "vertical", "shorts", "typography", "2026"),
        "style": "kinetic_type",
        "scenes": (
            ("STOP", "WORDS CAN HIT", "One phrase owns the first beat."),
            ("BUILD", "RHYTHM / SCALE / SPACE", "Stack words without losing mobile readability."),
            ("LAND", "MAKE IT MOVE", "Resolve on one branded action."),
        ),
    },
    {
        "id": "painterly_3d_character_spot",
        "name": "Painterly Character Spot",
        "category": "2026 Trends",
        "variants": ("16:9", "9:16"),
        "duration_ms": 12000,
        "cta": "MEET THE CHARACTER",
        "description": (
            "A stable painted character treatment for images, video, and "
            "existing AR/PBR render layers without requiring a new 3D engine."
        ),
        "features": (
            "Painterly Look", "Toon bands", "Stable ink lines",
            "Brush and paper texture", "Character media slots",
        ),
        "workflow": (
            "Character campaign, game promo, and stylized AR/PBR render spot"
        ),
        "replace_items": (
            "Character image/video/render", "Detail crop", "Headline", "CTA",
        ),
        "tags": (
            "painterly", "toon", "ink", "character", "ar pbr", "2026",
        ),
        "style": "painterly",
        "scenes": (
            ("SILHOUETTE", "A character with presence", "Start on a bold readable pose."),
            ("PAINT / INK", "Every line has intent", "Reveal texture without line popping."),
            ("IN MOTION", "Built for every frame", "Resolve on the character and invitation."),
        ),
    },
    {
        "id": "hot_2026_prompt_playground",
        "name": "Command Grid Kinetic Opener",
        "category": "Hot Motion 2026",
        "variants": ("16:9", "9:16", "1:1"),
        "duration_ms": 10000,
        "cta": "RUN THE IDEA",
        "description": "Retro productivity windows, cursor rhythm, data blocks, and tactile photocopy noise.",
        "features": ("Modular UI cards", "Cursor-like rhythm", "Photocopy texture", "Editable data copy"),
        "workflow": "AI product opener, technology ident, and creator-tool campaign",
        "replace_items": ("UI plate", "Prompt copy", "Status labels", "CTA"),
        "tags": ("prompt playground", "retro tech", "ui", "data", "2026"),
        "style": "collage",
        "asset_name": "prompt_playground.png",
        "scenes": (
            ("INPUT", "Ideas enter messy", "Open with stacked windows and an unfinished prompt."),
            ("PARSE", "Signals find a rhythm", "Turn fragments into ordered visual beats."),
            ("BUILD", "Systems become playful", "Let cards, cursors, and data blocks trade focus."),
            ("OUTPUT", "Make the tool feel human", "Resolve on one useful action instead of an AI spectacle."),
        ),
    },
    {
        "id": "hot_2026_reality_warp",
        "name": "Chrome Type Flow",
        "category": "Hot Motion 2026",
        "variants": ("16:9", "9:16"),
        "duration_ms": 8500,
        "cta": "SHIFT PERSPECTIVE",
        "description": "A surreal chrome product crosses refractive surfaces with controlled optical distortion.",
        "features": ("Refractive staging", "Macro product crop", "Depth parallax", "Chromatic edge accents"),
        "workflow": "Beauty, fashion, music, and premium product campaign",
        "replace_items": ("Hero object", "Macro crop", "Benefit copy", "CTA"),
        "tags": ("reality warp", "surreal", "chrome", "product", "2026"),
        "style": "glass",
        "asset_name": "reality_warp.png",
        "scenes": (
            ("REFRACT", "Reality bends first", "Begin inside the material, not outside it."),
            ("SURFACE", "Form changes with light", "Use scale and offset to reveal optical depth."),
            ("OBJECT", "One detail becomes the world", "Land on a clean product silhouette and invitation."),
        ),
    },
    {
        "id": "hot_2026_explorecore",
        "name": "Dynamic Poster Atlas",
        "category": "Hot Motion 2026",
        "variants": ("16:9", "9:16", "1:1"),
        "duration_ms": 11000,
        "cta": "FOLLOW THE MAP",
        "description": "Layered maps, archival photographs, quiet editorial pacing, and purposeful discovery.",
        "features": ("Layered storytelling", "Map and photo slots", "Editorial pacing", "Discovery chapters"),
        "workflow": "Travel story, documentary chapter, and cultural editorial",
        "replace_items": ("Landscape photos", "Map fragments", "Place names", "Closing note"),
        "tags": ("explorecore", "travel", "editorial", "maps", "2026"),
        "style": "story",
        "asset_name": "explorecore.png",
        "scenes": (
            ("DEPART", "Leave room to wonder", "Hold long enough for the landscape to become a place."),
            ("TRACE", "Every route keeps a memory", "Layer map evidence over the photographic field."),
            ("NOTICE", "Small details change the story", "Move from panorama to a tactile observation."),
            ("ARRIVE", "The map is not the destination", "Resolve with a calm location card."),
        ),
    },
    {
        "id": "hot_2026_texture_check",
        "name": "Carousel Macro Rush",
        "category": "Hot Motion 2026",
        "variants": ("16:9", "9:16", "1:1"),
        "duration_ms": 7500,
        "cta": "FEEL THE FLAVOR",
        "description": "Gloss, condensation, bubbles, and soft fabric turn a product macro into a sensory spot.",
        "features": ("Sensory macro", "Slow push-in", "Gloss highlights", "ASMR-ready cue points"),
        "workflow": "Food, beverage, skincare, and fragrance advertising",
        "replace_items": ("Macro image", "Flavor or material", "Sensory verbs", "CTA"),
        "tags": ("texture check", "sensory", "macro", "food", "2026"),
        "style": "craft",
        "asset_name": "texture_check.png",
        "scenes": (
            ("TOUCH", "Gloss you can almost feel", "Start close enough to remove ordinary scale."),
            ("TASTE", "Color becomes sensation", "Let bubbles and highlights carry the rhythm."),
            ("LINGER", "Keep the final note", "Hold the product promise instead of rushing the CTA."),
        ),
    },
    {
        "id": "hot_2026_notes_app_chic",
        "name": "Replay Rewind Collage",
        "category": "Hot Motion 2026",
        "variants": ("16:9", "9:16", "1:1"),
        "duration_ms": 9000,
        "cta": "KEEP THE ROUGH CUT",
        "description": "Unfinished notes, tape, graphite, and highlighter strokes preserve the human draft.",
        "features": ("Notebook surface", "Handmade attachments", "Imperfect timing", "Draft-to-decision arc"),
        "workflow": "Behind-the-scenes reel, process film, and creator announcement",
        "replace_items": ("Notebook image", "Draft notes", "Snapshot", "Final decision"),
        "tags": ("notes app chic", "raw", "notebook", "process", "2026"),
        "style": "collage",
        "asset_name": "notes_app_chic.png",
        "scenes": (
            ("NOTE 01", "Start before it is ready", "Let the first thought arrive with visible rough edges."),
            ("REVISION", "Cross out the obvious answer", "Use stepped timing so the edit feels touched."),
            ("PIN IT", "One fragment survives", "Attach the useful idea and remove the rest."),
            ("DECIDE", "Progress over polish", "Finish on the choice, not a perfect page."),
        ),
    },
    {
        "id": "hot_2026_opt_out_era",
        "name": "Nostalgic Future Editorial",
        "category": "Hot Motion 2026",
        "variants": ("16:9", "9:16", "1:1"),
        "duration_ms": 10500,
        "cta": "TAKE YOUR TIME",
        "description": "Restrained serif-led editorial motion uses silence, material, and negative space as content.",
        "features": ("Structured simplicity", "Long holds", "Material still life", "Minimal palette"),
        "workflow": "Luxury identity, architecture title, and considered brand film",
        "replace_items": ("Still-life plate", "Editorial title", "Short statement", "Signature"),
        "tags": ("opt out era", "minimal", "editorial", "luxury", "2026"),
        "style": "craft",
        "asset_name": "opt_out_era.png",
        "scenes": (
            ("01", "Less, held longer", "Let shadow and material establish the pace."),
            ("02", "Attention needs space", "Move only what changes the reading."),
            ("03", "Clarity is a luxury", "End with a quiet signature and no visual noise."),
        ),
    },
    {
        "id": "hot_2026_drama_club",
        "name": "Overdrive Stomp Opener",
        "category": "Hot Motion 2026",
        "variants": ("16:9", "9:16"),
        "duration_ms": 8200,
        "cta": "ENTER THE SCENE",
        "description": "A theatrical spotlight turns an ordinary announcement into a dramatic short-form event.",
        "features": ("Spotlight staging", "Curtain reveal", "Cinematic title scale", "Meta-story beats"),
        "workflow": "Entertainment promo, event opener, and dramatic social reveal",
        "replace_items": ("Hero footage", "Event title", "Date", "CTA"),
        "tags": ("drama club", "cinematic", "stage", "spotlight", "2026"),
        "style": "story",
        "asset_name": "drama_club.png",
        "scenes": (
            ("CURTAIN", "Every entrance deserves a scene", "Hold the dark stage before revealing the subject."),
            ("SPOTLIGHT", "Make the ordinary monumental", "Use one hard source and a controlled title hit."),
            ("TURN", "The audience knows the secret", "Break the fourth wall with one concise detail."),
            ("ENCORE", "Leave on the strongest frame", "Resolve with event, date, and action."),
        ),
    },
    {
        "id": "hot_2026_local_craft",
        "name": "Stamp-On Pattern Intro",
        "category": "Hot Motion 2026",
        "variants": ("16:9", "9:16", "1:1"),
        "duration_ms": 9500,
        "cta": "MADE HERE",
        "description": "Block-print geometry and imperfect ink motion combine regional craft with modern pacing.",
        "features": ("Block-print texture", "Modular pattern", "Local color system", "Stepped craft motion"),
        "workflow": "Cultural event, food identity, local business, and place branding",
        "replace_items": ("Pattern plate", "Local palette", "Place copy", "Maker mark"),
        "tags": ("local flavor", "block print", "craft", "culture", "2026"),
        "style": "craft",
        "asset_name": "local_craft.png",
        "scenes": (
            ("PLACE", "A pattern carries a memory", "Introduce one regional mark at human scale."),
            ("PRESS", "Ink keeps the maker visible", "Use small registration shifts instead of sterile loops."),
            ("GATHER", "Parts become a neighborhood", "Build the pattern through shared visual rhythm."),
            ("MARK", "Made here, moving forward", "Finish with a clear local signature."),
        ),
    },
    {
        "id": "hot_2026_variable_kinetic_type",
        "name": "3D Kinetic Punk Type",
        "category": "Hot Motion 2026",
        "variants": ("16:9", "9:16", "1:1"),
        "duration_ms": 7000,
        "cta": "TYPE WITH FORCE",
        "description": "Weight, width, scale, and word rhythm turn typography into the primary performer.",
        "features": ("Variable-axis intent", "Word cascade", "Optical rhythm", "High-energy title hits"),
        "workflow": "Music ident, sports opener, fashion title, and vertical hook",
        "replace_items": ("Hook words", "Font family", "Accent color", "Final command"),
        "tags": ("variable font", "kinetic typography", "type", "rhythm", "2026"),
        "style": "kinetic_type",
        "asset_name": "variable_kinetic_type.png",
        "scenes": (
            ("WIDE", "WORDS TAKE SPACE", "Stretch the phrase until it becomes architecture."),
            ("HEAVY", "RHYTHM HAS WEIGHT", "Trade width, scale, and silence on the beat."),
            ("HIT", "TYPE WITH FORCE", "Land on one command with no supporting clutter."),
        ),
    },
    {
        "id": "hot_2026_liquid_glass_next",
        "name": "Liquid Glass Titles",
        "category": "Hot Motion 2026",
        "variants": ("16:9", "9:16", "1:1"),
        "duration_ms": 8800,
        "cta": "MOVE THROUGH IT",
        "description": "Translucent controls occupy depth, refract context, and respond as a spatial interface system.",
        "features": ("Backdrop-aware glass", "Depth-stacked cards", "Gloss response", "UI motion choreography"),
        "workflow": "App launch, interface concept, product tour, and premium HUD",
        "replace_items": ("Backdrop", "Feature cards", "App copy", "Primary action"),
        "tags": ("liquid glass", "spatial ui", "glass", "app", "2026"),
        "style": "glass",
        "asset_name": "liquid_glass_next.png",
        "scenes": (
            ("DEPTH", "Controls enter the scene", "Separate interface layers without losing context."),
            ("REFRACT", "The backdrop remains alive", "Let glass respond to what passes behind it."),
            ("FOCUS", "One surface becomes active", "Reduce the stack as the task becomes clear."),
            ("ACT", "Move through it", "Resolve on a precise glossy action."),
        ),
    },
)

_SPECS = {str(item["id"]): item for item in TREND_TEMPLATE_SPECS}


def is_trend_template(template_id: str) -> bool:
    return str(template_id) in _SPECS


def _behavior(kind: str, duration_ms: int, **params: Any) -> MotionBehaviorRef:
    return MotionBehaviorRef(
        kind=kind,
        start_ms=0,
        end_ms=max(1, min(duration_ms, 650)),
        params=params,
    )


def _shape(
    name: str,
    *,
    width: float,
    height: float,
    x: float,
    y: float,
    color: str,
    start_ms: int,
    end_ms: int,
    role: str,
    radius: float = 0.0,
) -> MotionLayer:
    layer = MotionLayer(
        name=name,
        layer_type="shape",
        in_ms=start_ms,
        out_ms=end_ms,
        source=SourceRef(kind="shape", params={
            "shape": "rectangle",
            "width": width,
            "height": height,
            "fill": color,
            "stroke": "#00000000",
            "stroke_width": 0,
            "radius": radius,
        }),
        metadata={"template_role": role, "trend_template": True},
    )
    layer.transform.position.default = [x, y]
    return layer


def _text(
    name: str,
    text: str,
    *,
    x: float,
    y: float,
    size: float,
    color: str,
    start_ms: int,
    end_ms: int,
    role: str,
    align: str,
    box_width: float,
) -> MotionLayer:
    unit = "word" if role in {"headline", "body"} else "character"
    layer = MotionLayer(
        name=name,
        layer_type="text",
        in_ms=start_ms,
        out_ms=end_ms,
        source=SourceRef(kind="typography", params={
            "text": text,
            "font_family": "Segoe UI",
            "font_size": size,
            "font_weight": 800 if role == "headline" else 600,
            "fill": color,
            "align": align,
            "width": max(120.0, float(box_width)),
            "height": size * 3.0,
            "text_animation": {
                "in": "slide-up-in",
                "hold": "none",
                "out": "fade-out",
                "unit": unit,
                "stagger_ms": 38 if unit == "word" else 22,
                "in_duration_ms": 420,
                "out_duration_ms": 280,
            },
        }),
        metadata={"template_role": role, "trend_template": True},
    )
    layer.transform.position.default = [x, y]
    layer.behaviors.append(_behavior("fade", end_ms - start_ms, direction="in", hold_after=True))
    return layer


def build_trend_template_layers(
    template_id: str,
    width: int,
    height: int,
    controls: Mapping[str, Any],
) -> list[MotionLayer]:
    spec = _SPECS[str(template_id)]
    if is_hot_trend_template(template_id):
        return build_hot_trend_template_layers(
            template_id,
            spec,
            width,
            height,
            controls,
        )
    scenes = tuple(spec["scenes"])
    duration = int(controls["duration_ms"])
    accent = str(controls["accent_color"])
    surface = str(controls["surface_color"])
    headline = str(controls["headline"])
    subtitle = str(controls["subtitle"])
    cta = str(controls.get("cta") or spec["cta"])
    landscape = width >= height
    text_anchor = width * (0.28 if landscape else 0.50)
    text_box_width = width * (0.42 if landscape else 0.82)
    media_x = width * (0.73 if landscape else 0.50)
    media_y = height * (0.50 if landscape else 0.63)
    media_w = width * (0.40 if landscape else 0.78)
    media_h = height * (0.66 if landscape else 0.42)
    align = "left" if landscape else "center"
    title_size = min(width, height) * (0.075 if landscape else 0.064)
    layers = [
        _shape(
            "Trend Background",
            width=width,
            height=height,
            x=width * 0.5,
            y=height * 0.5,
            color=surface,
            start_ms=0,
            end_ms=duration,
            role="background",
        )
    ]
    for index, (kicker, scene_title, body) in enumerate(scenes):
        start = round(duration * index / len(scenes))
        end = round(duration * (index + 1) / len(scenes))
        if index == 0:
            scene_title, body = headline, subtitle
        elif index == len(scenes) - 1:
            body = f"{body}  {cta}"
        group = MotionLayer(
            name=f"Trend Scene {index + 1:02d}",
            layer_type="group",
            in_ms=start,
            out_ms=end,
            metadata={
                "template_role": "scene",
                "scene_index": index + 1,
                "scene_name": kicker,
                "trend_template": True,
            },
        )
        layers.append(group)
        media = _shape(
            f"Scene {index + 1} Replace Media",
            width=media_w,
            height=media_h,
            x=media_x,
            y=media_y,
            color=f"{accent[:7]}B8",
            start_ms=start,
            end_ms=end,
            role="media_slot",
            radius=min(width, height) * (0.026 if spec["style"] == "glass" else 0.008),
        )
        media.parent_id = group.id
        media.behaviors.append(
            _behavior(
                "pop" if spec["style"] in {"stop_motion", "kinetic_type"} else "slide",
                end - start,
                **({"from": 0.84, "overshoot": 0.10, "hold_after": True}
                   if spec["style"] in {"stop_motion", "kinetic_type"}
                   else {"direction": "in", "distance": [width * 0.035, 0], "hold_after": True}),
            )
        )
        if spec["style"] == "glass":
            glass = make_glass_effect(
                preset="liquid_cta" if index == len(scenes) - 1 else "frosted",
            )
            glass.metadata["driver"] = {
                "source": "pointer",
                "strength": 1.15 if index < len(scenes) - 1 else 1.5,
            }
            media.effects.append(glass)
        elif spec["style"] in {"craft", "collage", "vhs", "stop_motion"}:
            preset = {
                "craft": "luxury_paper",
                "collage": "printed_poster",
                "vhs": "vhs_tape",
                "stop_motion": "handmade",
            }[str(spec["style"])]
            media.effects.append(make_craft_style_effect({"seed": 20260729 + index}, preset=preset))
        elif spec["style"] == "painterly":
            preset = ("painted", "ink", "toon")[index % 3]
            media.effects.append(make_painterly_look_effect(
                {"seed": 20260729 + index},
                preset=preset,
            ))
        layers.append(media)
        if spec["style"] == "glass":
            for row_index in range(3):
                row = _shape(
                    f"Scene {index + 1} App Row {row_index + 1}",
                    width=media_w * (0.72 - row_index * 0.07),
                    height=media_h * 0.075,
                    x=media_x,
                    y=media_y + media_h * (-0.20 + row_index * 0.20),
                    color="#dff7ff66" if row_index != 1 else f"{accent[:7]}99",
                    start_ms=start,
                    end_ms=end,
                    role="app_control",
                    radius=min(width, height) * 0.012,
                )
                row.parent_id = group.id
                layers.append(row)
        elif spec["style"] == "collage":
            tape = _shape(
                f"Scene {index + 1} Tape",
                width=media_w * 0.28,
                height=media_h * 0.075,
                x=media_x,
                y=media_y - media_h * 0.50,
                color="#f3e5b899",
                start_ms=start,
                end_ms=end,
                role="attachment",
            )
            tape.parent_id = group.id
            tape.transform.rotation.default = -7.0 if index % 2 == 0 else 6.0
            layers.append(tape)
        elif spec["style"] == "stop_motion":
            head_size = min(media_w, media_h) * 0.42
            head = _shape(
                f"Scene {index + 1} Mascot Head",
                width=head_size,
                height=head_size,
                x=media_x,
                y=media_y - media_h * 0.04,
                color="#e8a26f",
                start_ms=start,
                end_ms=end,
                role="mascot_slot",
                radius=head_size * 0.5,
            )
            head.source.params["shape"] = "ellipse"
            head.parent_id = group.id
            layers.append(head)
            for eye_index in (-1, 1):
                eye = _shape(
                    f"Scene {index + 1} Mascot Eye {eye_index:+d}",
                    width=head_size * 0.10,
                    height=head_size * 0.14,
                    x=media_x + eye_index * head_size * 0.16,
                    y=media_y - media_h * 0.08,
                    color="#2a2024",
                    start_ms=start,
                    end_ms=end,
                    role="mascot_detail",
                    radius=head_size * 0.05,
                )
                eye.source.params["shape"] = "ellipse"
                eye.parent_id = group.id
                layers.append(eye)
        elif spec["style"] == "kinetic_type":
            for bar_index in range(3):
                bar = _shape(
                    f"Scene {index + 1} Rhythm Bar {bar_index + 1}",
                    width=media_w * (0.82 - bar_index * 0.17),
                    height=max(10.0, media_h * 0.06),
                    x=width * (0.50 + (bar_index - 1) * 0.04),
                    y=media_y + media_h * (-0.20 + bar_index * 0.20),
                    color=accent if bar_index == 1 else "#f4f7fa",
                    start_ms=start,
                    end_ms=end,
                    role="rhythm_bar",
                )
                bar.parent_id = group.id
                bar.behaviors.append(_behavior("slide", end - start, direction="in", distance=[0, 60], hold_after=True))
                layers.append(bar)
        elif spec["style"] == "painterly":
            portrait_size = min(media_w, media_h)
            body = _shape(
                f"Scene {index + 1} Character Body",
                width=portrait_size * 0.48,
                height=portrait_size * 0.58,
                x=media_x,
                y=media_y + portrait_size * 0.20,
                color=("#b75345", "#3d6879", "#7a557d")[index % 3],
                start_ms=start,
                end_ms=end,
                role="character_preview",
                radius=portrait_size * 0.11,
            )
            head = _shape(
                f"Scene {index + 1} Character Head",
                width=portrait_size * 0.36,
                height=portrait_size * 0.40,
                x=media_x,
                y=media_y - portrait_size * 0.16,
                color="#e9c6a2",
                start_ms=start,
                end_ms=end,
                role="character_preview",
                radius=portrait_size * 0.18,
            )
            head.source.params["shape"] = "ellipse"
            hair = _shape(
                f"Scene {index + 1} Character Hair",
                width=portrait_size * 0.43,
                height=portrait_size * 0.29,
                x=media_x,
                y=media_y - portrait_size * 0.26,
                color=("#273c57", "#3a2d3f", "#173d42")[index % 3],
                start_ms=start,
                end_ms=end,
                role="character_preview",
                radius=portrait_size * 0.14,
            )
            hair.source.params["shape"] = "ellipse"
            for preview_index, preview in enumerate((body, head, hair)):
                preview.parent_id = group.id
                preview.effects.append(make_painterly_look_effect(
                    {"seed": 20260820 + index * 5 + preview_index},
                    preset=("painted", "ink", "toon")[index % 3],
                ))
                layers.append(preview)
        kicker_layer = _text(
            f"Scene {index + 1} Kicker",
            str(kicker),
            x=text_anchor if landscape else width * 0.5,
            y=height * (0.24 if landscape else 0.16),
            size=title_size * 0.28,
            color=accent,
            start_ms=start,
            end_ms=end,
            role="kicker",
            align=align,
            box_width=text_box_width,
        )
        title = _text(
            f"Scene {index + 1} Headline",
            str(scene_title),
            x=text_anchor if landscape else width * 0.5,
            y=height * (0.40 if landscape else 0.30),
            size=title_size,
            color="#f4f7fa",
            start_ms=start,
            end_ms=end,
            role="headline",
            align=align,
            box_width=text_box_width,
        )
        body_layer = _text(
            f"Scene {index + 1} Body",
            str(body),
            x=text_anchor if landscape else width * 0.5,
            y=height * (0.57 if landscape else 0.43),
            size=title_size * 0.34,
            color="#b9c3cd",
            start_ms=start,
            end_ms=end,
            role="body",
            align=align,
            box_width=text_box_width,
        )
        for child in (kicker_layer, title, body_layer):
            child.parent_id = group.id
            child.metadata["safe_area"] = "platform"
            layers.append(child)
        if not landscape:
            for child in (kicker_layer, title, body_layer):
                child.source.params["width"] = width * 0.82
        if spec["style"] == "collage":
            media.transform.rotation = AnimatedProperty(
                default=(-4.0 if index % 2 == 0 else 3.0),
            )
            media.metadata["collage_item"] = {
                "schema": "tigerstudio.motion.collage.v1",
                "edge": "torn",
                "attachment": "tape" if index != 1 else "staple",
                "template_managed": True,
            }
        if spec["style"] == "kinetic_type":
            title.transform.scale = AnimatedProperty(
                value_type="vector2",
                default=[0.74, 0.74],
                keyframes=[
                    Keyframe(time_ms=0, value=[0.74, 0.74], interpolation="bezier"),
                    Keyframe(time_ms=min(430, end - start), value=[1.08, 1.08], interpolation="bezier"),
                    Keyframe(time_ms=min(620, end - start), value=[1.0, 1.0], interpolation="bezier"),
                ],
            )
    if str(spec["style"]) in {"craft", "vhs"}:
        layers[0].effects.append(
            make_craft_style_effect(
                {"seed": 20260729},
                preset="luxury_paper" if spec["style"] == "craft" else "vhs_tape",
            )
        )
    if str(spec["style"]) == "painterly":
        layers[0].effects.append(make_painterly_look_effect(
            {
                "amount": 0.24,
                "brush_amount": 0.16,
                "paper_amount": 0.18,
                "edge_strength": 0.0,
                "seed": 20260729,
            },
            preset="paper",
        ))
    return layers


def clear_managed_trend_state(composition: MotionComposition) -> None:
    state = composition.metadata.get(TREND_TEMPLATE_STATE_KEY)
    if not isinstance(state, Mapping):
        return
    for key in ("stop_motion", "story_direction"):
        value = composition.metadata.get(key)
        if isinstance(value, Mapping) and value.get("trend_template_managed"):
            composition.metadata.pop(key, None)
    composition.metadata.pop(TREND_TEMPLATE_STATE_KEY, None)


def configure_trend_template(
    composition: MotionComposition,
    template_id: str,
    layer_ids: list[str],
) -> dict[str, Any]:
    spec = _SPECS[str(template_id)]
    selected = [layer for layer in composition.layers if layer.id in set(layer_ids)]
    style = str(spec["style"])
    if style == "stop_motion":
        target_ids = [
            layer.id for layer in selected
            if layer.metadata.get("template_role") in {"media_slot", "headline"}
        ]
        set_stop_motion(
            composition,
            {
                "enabled": True,
                "exposure_frames": 2,
                "pose_jitter_px": 1.4,
                "rotation_jitter_deg": 0.55,
                "material_boil": 0.22,
                "motion_style": "contact_settle",
                "seed": 20260729,
            },
            layer_ids=target_ids,
        )
        for layer_id in target_ids:
            set_stop_motion_material(
                composition,
                [layer_id],
                preset="clay",
                seed=20260729,
            )
    if style == "story":
        update_story(
            composition,
            {
                "title": str(spec["name"]),
                "message": "Human action turns distance into visible progress.",
                "audience": "Purpose-led brand audience",
                "character_continuity": {"primary": "hero", "direction": "motivated"},
            },
        )
        scene_layers = [
            layer for layer in selected
            if layer.metadata.get("template_role") == "scene"
        ]
        roles = ("hook", "conflict", "reveal", "proof", "cta")
        for role, scene in zip(roles, scene_layers):
            add_story_beat(
                composition,
                role=role,
                start_ms=scene.in_ms,
                end_ms=scene.out_ms,
                purpose=str(scene.metadata.get("scene_name") or role).title(),
                emotion="resolve" if role == "cta" else "human",
                character="hero",
                audio_cue=f"{role}_cue",
                scene_id=scene.id,
                layer_ids=[
                    layer.id for layer in selected
                    if layer.parent_id == scene.id
                ],
            )
        composition.metadata["story_direction"]["trend_template_managed"] = True
    state = {
        "schema": TREND_TEMPLATE_SCHEMA,
        "template_id": str(template_id),
        "style": style,
        "layer_ids": list(layer_ids),
        "editable": True,
        "preview_renderer": "MotionExportRenderer",
        "fallbacks": (
            ["shared_raster_cpu:glass"] if style == "glass" else []
        ),
    }
    composition.metadata[TREND_TEMPLATE_STATE_KEY] = deepcopy(state)
    return state


def trend_template_capabilities() -> dict[str, Any]:
    return {
        "schema": "tigerstudio.motion.trend_template_capabilities.v1",
        "available_template_ids": [str(item["id"]) for item in TREND_TEMPLATE_SPECS],
        "blocked": [],
        "notes": [{
            "id": "painterly_3d_character_spot",
            "scope": "provider_neutral_post_render",
            "input": "image, video, or existing AR/PBR render layer",
            "material_id_overrides": "requires an upstream material-ID pass",
        }],
    }


def preflight_trend_templates(template_id: str = "") -> dict[str, Any]:
    from app.unreal_umg_document import motion_composition_to_umg_document

    from .templates import get_template, instantiate_template
    from .validation import validate_composition

    requested = str(template_id or "").strip()
    template_ids = [requested] if requested else [
        str(item["id"]) for item in TREND_TEMPLATE_SPECS
    ]
    unknown = [item for item in template_ids if item not in _SPECS]
    if unknown:
        raise ValueError(f"unknown 2026 trend template: {unknown[0]}")
    rows = []
    for current_id in template_ids:
        template = get_template(current_id)
        variants = []
        for variant in template.variants:
            composition = instantiate_template(current_id, variant=variant)
            validation = validate_composition(composition)
            document = motion_composition_to_umg_document(composition)
            blocked = [
                row for row in document["Layers"]
                if row["Disposition"] == "Blocked"
            ]
            variants.append({
                "variant": variant,
                "valid": validation.ok,
                "issue_count": len(validation.issues),
                "layer_count": len(composition.layers),
                "scene_count": template.scene_count,
                "umg_blocked_layer_count": len(blocked),
                "umg_block_reasons_explicit": all(
                    "umg_block_reasons" in row["PayloadJson"]
                    for row in blocked
                ),
            })
        rows.append({
            "template_id": current_id,
            "variants": variants,
            "ok": all(
                row["valid"] and row["umg_block_reasons_explicit"]
                for row in variants
            ),
        })
    capabilities = trend_template_capabilities()
    return {
        "schema": "tigerstudio.motion.trend_template_preflight.v1",
        "ok": all(row["ok"] for row in rows),
        "templates": rows,
        "blocked_capabilities": capabilities["blocked"],
        "summary": {
            "template_count": len(rows),
            "variant_count": sum(len(row["variants"]) for row in rows),
            "blocked_capability_count": len(capabilities["blocked"]),
        },
    }


__all__ = [
    "TREND_TEMPLATE_SCHEMA",
    "TREND_TEMPLATE_SPECS",
    "TREND_TEMPLATE_STATE_KEY",
    "build_trend_template_layers",
    "clear_managed_trend_state",
    "configure_trend_template",
    "is_trend_template",
    "preflight_trend_templates",
    "trend_template_capabilities",
]
