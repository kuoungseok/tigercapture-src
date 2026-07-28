"""Built-in Motion Designer templates with stable published controls."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping

from .particles import create_particle_layer
from .schema import (
    AnimatedProperty,
    Keyframe,
    MotionBehaviorRef,
    MotionComposition,
    MotionLayer,
    SourceRef,
    new_motion_id,
)


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
    description: str = ""
    features: tuple[str, ...] = ()
    tutorial_steps: tuple[str, ...] = ()
    difficulty: str = "Starter"
    estimated_minutes: int = 0
    scene_count: int = 1
    workflow: str = "Quick graphic"
    replace_items: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": TEMPLATE_SCHEMA, "id": self.id, "name": self.name,
            "category": self.category, "variants": list(self.variants),
            "published_controls": [item.to_dict() for item in self.controls],
            "realtime_grade": self.realtime_grade,
            "description": self.description,
            "features": list(self.features),
            "tutorial_steps": list(self.tutorial_steps),
            "difficulty": self.difficulty,
            "estimated_minutes": int(self.estimated_minutes),
            "is_tutorial": bool(self.tutorial_steps),
            "scene_count": int(self.scene_count),
            "workflow": self.workflow,
            "replace_items": list(self.replace_items),
            "tags": list(self.tags),
            "default_duration_ms": int(
                next(
                    (
                        control.default
                        for control in self.controls
                        if control.id == "duration_ms"
                    ),
                    4000,
                )
            ),
        }


COMMON_CONTROLS = (
    PublishedControl("headline", "Headline", "string", "TIGER STUDIO"),
    PublishedControl("subtitle", "Subtitle", "string", "MOTION DESIGN"),
    PublishedControl("accent_color", "Accent", "color", "#43d7b5"),
    PublishedControl("surface_color", "Surface", "color", "#10151c"),
    PublishedControl("duration_ms", "Duration", "integer", 4000),
)


def _production_controls(
    duration_ms: int,
    *,
    cta: str = "LEARN MORE",
) -> tuple[PublishedControl, ...]:
    return (
        *COMMON_CONTROLS[:-1],
        PublishedControl("cta", "Call to action", "string", cta),
        PublishedControl("duration_ms", "Duration", "integer", duration_ms),
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
    MotionTemplate(
        "learn_keyframes_graph",
        "Learn 01 - Keyframes and Graph",
        "Learn",
        tuple(TEMPLATE_VARIANTS),
        COMMON_CONTROLS,
        description="A working scene that demonstrates position, scale, rotation, easing, and motion blur.",
        features=("Transform keyframes", "Bezier easing", "Graph Editor", "Motion blur", "Layer timing"),
        tutorial_steps=(
            "Play the composition and watch the Focus Card move between three keyframes.",
            "Select Focus Card, expand Position, then compare its keyframes in the Graph Editor.",
            "Drag the middle keyframe vertically and replay to see the changed motion arc.",
            "Inspect Rotation, Scale, and the layer Motion Blur metadata.",
        ),
        estimated_minutes=4,
    ),
    MotionTemplate(
        "learn_typography_vector",
        "Learn 02 - Type and Vector",
        "Learn",
        tuple(TEMPLATE_VARIANTS),
        COMMON_CONTROLS,
        description="Editable animated typography combined with a vector path, trim animation, and hierarchy.",
        features=("Typography animation", "Word stagger", "Vector path", "Trim path", "Parent hierarchy"),
        tutorial_steps=(
            "Play once to see the headline animate by word.",
            "Select Tutorial Headline and change Text Animation from word to character.",
            "Select Drawn Accent and edit its path handles directly in the canvas.",
            "Open the Vector inspector and adjust trim End to reveal more or less of the line.",
        ),
        estimated_minutes=5,
    ),
    MotionTemplate(
        "learn_particles_composite",
        "Learn 03 - Particles and Composite",
        "Learn",
        tuple(TEMPLATE_VARIANTS),
        COMMON_CONTROLS,
        "cached",
        description="A layered burst showing particles, blend modes, deterministic seeds, and depth ordering.",
        features=("Particle emitter", "Burst timing", "Screen blend", "Layer order", "Cached preview"),
        tutorial_steps=(
            "Play from frame zero and inspect the deterministic particle burst.",
            "Select Tutorial Particles and change Birth Rate or the burst Count.",
            "Toggle its Screen blend mode to Normal and compare the composite.",
            "Move the Glow Disc above and below the title to learn layer ordering.",
        ),
        estimated_minutes=4,
    ),
    MotionTemplate(
        "learn_interactive_unreal_button",
        "Learn 04 - Interactive Unreal Button",
        "Learn",
        tuple(TEMPLATE_VARIANTS),
        COMMON_CONTROLS,
        description="An interactive CTA with hover, pressed, focused, and disabled states ready for Unreal Link.",
        features=("Button component", "Hover and press states", "Spring transition", "Click event", "Unreal UMG export"),
        tutorial_steps=(
            "Move the pointer over the CTA and press it to preview its states.",
            "Select CTA Button and open the Button inspector.",
            "Adjust Hover Scale, Pressed Offset, and Transition timing.",
            "Open Unreal Link and generate the editable Widget Blueprint for a connected project.",
        ),
        difficulty="Intermediate",
        estimated_minutes=6,
    ),
    MotionTemplate(
        "learn_generators_replicators",
        "Learn 05 - Generators and Replicators",
        "Learn",
        tuple(TEMPLATE_VARIANTS),
        COMMON_CONTROLS,
        description="A procedural background and radial pattern that remain fully editable.",
        features=("Procedural Generator", "Radial Replicator", "Per-copy scale", "Opacity falloff"),
        tutorial_steps=(
            "Select Procedural Gradient and open the Generator inspector.",
            "Switch Gradient to Grid, Noise, or Rays and adjust Scale.",
            "Select Replicated Star and open the Replicator inspector.",
            "Compare Line, Grid, and Radial arrangements, then change Copies and Offset.",
        ),
        estimated_minutes=4,
    ),
    MotionTemplate(
        "ios_app_ui_motion_kit",
        "iOS App UI Motion Kit",
        "UI & Product",
        ("9:16", "16:9"),
        _production_controls(24000, cta="OPEN APP"),
        description=(
            "A five-scene, system-inspired iPhone product tour with status/navigation "
            "chrome, cards, lists, controls, a notification, a bottom sheet, and CTA."
        ),
        features=(
            "5 editable app scenes",
            "Navigation and tab bars",
            "Cards, list rows, toggles, progress, and buttons",
            "Notification and bottom sheet states",
            "Device-safe spacing",
        ),
        difficulty="Intermediate",
        estimated_minutes=12,
        scene_count=5,
        workflow="App prototype and launch demo",
        replace_items=("App name", "Feature copy", "Screenshots or illustrations", "CTA"),
        tags=("ios", "iphone", "mobile", "ui kit", "app", "product tour"),
    ),
    MotionTemplate(
        "mobile_onboarding_flow",
        "Mobile Onboarding Flow",
        "UI & Product",
        ("9:16", "16:9"),
        _production_controls(15000, cta="GET STARTED"),
        description=(
            "Four connected onboarding screens covering welcome, permissions, "
            "personalization, and completion."
        ),
        features=("4-screen flow", "Progress indicator", "Permission card", "Choice chips", "Completion CTA"),
        difficulty="Starter",
        estimated_minutes=8,
        scene_count=4,
        workflow="Mobile onboarding prototype",
        replace_items=("App name", "Onboarding copy", "Feature artwork", "CTA"),
        tags=("mobile", "onboarding", "prototype", "permissions"),
    ),
    MotionTemplate(
        "responsive_saas_product_tour",
        "Responsive SaaS Product Tour",
        "UI & Product",
        ("16:9", "9:16"),
        _production_controls(20000, cta="START FREE"),
        description=(
            "A four-part desktop product walkthrough with browser shell, dashboard, "
            "analytics detail, collaboration state, and final signup."
        ),
        features=("Browser shell", "Dashboard cards", "Chart placeholder", "Collaboration comments", "Responsive vertical cut"),
        difficulty="Intermediate",
        estimated_minutes=14,
        scene_count=4,
        workflow="Website and SaaS feature demo",
        replace_items=("Product name", "Dashboard media", "Metrics", "CTA"),
        tags=("saas", "dashboard", "website", "product tour", "analytics"),
    ),
    MotionTemplate(
        "product_launch_ad_15s",
        "Product Launch Ad - 15 Seconds",
        "Advertising",
        tuple(TEMPLATE_VARIANTS),
        _production_controls(15000, cta="SHOP NOW"),
        description=(
            "A complete five-beat launch spot: hook, product reveal, benefits, "
            "proof, and branded CTA."
        ),
        features=("5 advertising beats", "Product media slots", "Benefit cards", "Proof metric", "End card"),
        difficulty="Starter",
        estimated_minutes=10,
        scene_count=5,
        workflow="Paid social and product launch",
        replace_items=("Product media", "Hook", "Three benefits", "Proof", "CTA"),
        tags=("advertising", "product", "launch", "15 second", "social"),
    ),
    MotionTemplate(
        "vertical_social_ad_15s",
        "Vertical Social Ad - 15 Seconds",
        "Advertising",
        ("9:16", "1:1"),
        _production_controls(15000, cta="SWIPE UP"),
        description=(
            "A mobile-first performance ad with safe-zone copy, fast media cuts, "
            "offer card, testimonial proof, and CTA."
        ),
        features=("Vertical safe zones", "Fast-cut media slots", "Offer badge", "Testimonial card", "CTA end card"),
        difficulty="Starter",
        estimated_minutes=9,
        scene_count=5,
        workflow="Short-form paid social",
        replace_items=("Three vertical clips", "Offer", "Quote", "CTA"),
        tags=("vertical", "reels", "shorts", "ad", "15 second"),
    ),
    MotionTemplate(
        "campaign_story_ad_30s",
        "Campaign Story Ad - 30 Seconds",
        "Advertising",
        tuple(TEMPLATE_VARIANTS),
        _production_controls(30000, cta="DISCOVER MORE"),
        "cached",
        description=(
            "A six-scene narrative campaign with problem, context, transformation, "
            "feature proof, social proof, and end card."
        ),
        features=("6-scene story arc", "Editorial media framing", "Problem/solution contrast", "Quote and metric proof", "Campaign end card"),
        difficulty="Intermediate",
        estimated_minutes=18,
        scene_count=6,
        workflow="Brand campaign and explainer ad",
        replace_items=("Six media clips", "Narrative copy", "Proof points", "Logo", "CTA"),
        tags=("campaign", "brand", "story", "30 second", "commercial"),
    ),
    MotionTemplate(
        "course_module_opener_20s",
        "Course Module Opener - 20 Seconds",
        "Education",
        ("16:9", "9:16"),
        _production_controls(20000, cta="BEGIN LESSON"),
        description=(
            "A four-scene lesson opener introducing the topic, learning objectives, "
            "instructor, and chapter start."
        ),
        features=("Module title", "Learning objectives", "Instructor card", "Chapter marker", "Caption-safe layout"),
        difficulty="Starter",
        estimated_minutes=9,
        scene_count=4,
        workflow="Course and training opener",
        replace_items=("Course title", "Objectives", "Instructor", "Chapter name"),
        tags=("education", "course", "lesson", "training", "opener"),
    ),
    MotionTemplate(
        "step_by_step_tutorial_45s",
        "Step-by-Step Tutorial - 45 Seconds",
        "Education",
        ("16:9", "9:16"),
        _production_controls(45000, cta="TRY IT NOW"),
        description=(
            "A six-stage how-to structure with setup, three demonstrated steps, "
            "checklist recap, and practice CTA."
        ),
        features=("6 chapter scenes", "Numbered steps", "Demo media slots", "Checklist recap", "Progress rail"),
        difficulty="Intermediate",
        estimated_minutes=16,
        scene_count=6,
        workflow="Software tutorial and how-to",
        replace_items=("Demo captures", "Step titles", "Instructions", "Checklist", "CTA"),
        tags=("education", "tutorial", "how to", "45 second", "steps"),
    ),
    MotionTemplate(
        "lesson_explainer_60s",
        "Lesson Explainer - 60 Seconds",
        "Education",
        ("16:9", "9:16"),
        _production_controls(60000, cta="CONTINUE LEARNING"),
        "cached",
        description=(
            "An eight-scene micro-lesson with question, concept, examples, diagram, "
            "comparison, knowledge check, summary, and next lesson."
        ),
        features=("8-scene lesson plan", "Diagram and comparison layouts", "Knowledge check", "Summary cards", "Chapter progress"),
        difficulty="Intermediate",
        estimated_minutes=22,
        scene_count=8,
        workflow="Microlearning and classroom video",
        replace_items=("Lesson copy", "Examples", "Diagram media", "Quiz choices", "Next lesson"),
        tags=("education", "explainer", "microlearning", "quiz", "60 second"),
    ),
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
    for control in template.controls:
        if control.value_type in {"string", "color"}:
            result[control.id] = str(result[control.id])
    return result


def _behavior(kind: str, duration: int, **params: Any) -> MotionBehaviorRef:
    return MotionBehaviorRef(kind=kind, start_ms=0, end_ms=max(1, min(duration, 700)), params=params)


def _keyframed(default: Any, value_type: str, rows: list[tuple[int, Any, str]]) -> AnimatedProperty:
    return AnimatedProperty(
        value_type=value_type,
        default=deepcopy(default),
        keyframes=[
            Keyframe(time_ms=time_ms, value=deepcopy(value), interpolation=interpolation)
            for time_ms, value, interpolation in rows
        ],
    )


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


_PRODUCTION_STORYBOARDS: dict[str, tuple[tuple[str, str, str], ...]] = {
    "ios_app_ui_motion_kit": (
        ("01 / WELCOME", "Your day, organized", "A focused home screen with live status and quick actions."),
        ("02 / DISCOVER", "Everything in reach", "Navigation, search, cards, lists, and system controls."),
        ("03 / DETAIL", "See what matters", "Detail content, progress, toggles, and contextual actions."),
        ("04 / RESPOND", "Stay in the flow", "Notification and bottom-sheet states without losing context."),
        ("05 / READY", "Built for every moment", "One clear action completes the product tour."),
    ),
    "mobile_onboarding_flow": (
        ("WELCOME", "Meet your new workspace", "Start with one clear promise and a calm visual."),
        ("PERMISSIONS", "You stay in control", "Explain why access is needed before requesting it."),
        ("PERSONALIZE", "Make it yours", "Choose goals, interests, and a comfortable starting point."),
        ("COMPLETE", "Everything is ready", "Confirm setup and move directly into the product."),
    ),
    "responsive_saas_product_tour": (
        ("OVERVIEW", "One place for the whole team", "Introduce the dashboard and primary workflow."),
        ("INSIGHT", "Turn activity into answers", "Focus on analytics, trends, and decisions."),
        ("COLLABORATE", "Work together in context", "Comments, owners, status, and handoff remain attached."),
        ("LAUNCH", "From setup to value, faster", "Close with the plan and a direct signup action."),
    ),
    "product_launch_ad_15s": (
        ("HOOK", "The wait is over", "Open on one bold promise."),
        ("REVEAL", "Designed to stand apart", "Give the product a clean hero moment."),
        ("BENEFIT", "Faster. Smarter. Simpler.", "Show three benefits in one readable beat."),
        ("PROOF", "Trusted where it matters", "Add a metric, review, or recognizable result."),
        ("ACTION", "Make it yours today", "Finish with offer, brand, and CTA."),
    ),
    "vertical_social_ad_15s": (
        ("STOP SCROLLING", "This changes your routine", "Lead with the result, not the setup."),
        ("WATCH", "See it in action", "Use a close, readable vertical media cut."),
        ("OFFER", "More value, less effort", "Show the offer before attention drops."),
        ("PROOF", "People notice the difference", "Use one short quote or metric."),
        ("ACT NOW", "Ready when you are", "Keep the CTA inside platform safe zones."),
    ),
    "campaign_story_ad_30s": (
        ("THE PROBLEM", "Too much work, too little progress", "Establish a recognizable tension."),
        ("THE MOMENT", "There is a better way", "Shift tone and introduce possibility."),
        ("THE CHANGE", "A new rhythm begins", "Show the product transforming the workflow."),
        ("THE PROOF", "Results you can measure", "Demonstrate features and one concrete metric."),
        ("THE VOICE", "Built around real people", "Ground the claim with a human quote."),
        ("THE INVITATION", "Start your next chapter", "Resolve the story with a branded action."),
    ),
    "course_module_opener_20s": (
        ("MODULE", "Build a strong foundation", "Introduce the lesson and why it matters."),
        ("OBJECTIVES", "What you will learn", "Present three measurable outcomes."),
        ("INSTRUCTOR", "Learn with a clear guide", "Add instructor, role, and course context."),
        ("CHAPTER 01", "Let us begin", "Transition directly into the first lesson."),
    ),
    "step_by_step_tutorial_45s": (
        ("SETUP", "Prepare the workspace", "Show the final goal and required starting state."),
        ("STEP 01", "Create the base", "Demonstrate the first action with one visual focus."),
        ("STEP 02", "Refine the result", "Introduce the key adjustment and why it matters."),
        ("STEP 03", "Finish with confidence", "Complete the workflow and show the expected state."),
        ("RECAP", "Three steps to remember", "Summarize the sequence as a practical checklist."),
        ("PRACTICE", "Now try it yourself", "Give the learner a direct next action."),
    ),
    "lesson_explainer_60s": (
        ("QUESTION", "Why does this matter?", "Open with the problem the learner will solve."),
        ("CONCEPT", "The core idea", "Explain one principle in plain language."),
        ("EXAMPLE A", "See the pattern", "Use a concrete example before adding complexity."),
        ("DIAGRAM", "How the parts connect", "Map the relationship in a visual model."),
        ("COMPARE", "Choose the right approach", "Contrast two options with clear criteria."),
        ("CHECK", "What would you do?", "Pause for a quick knowledge check."),
        ("SUMMARY", "The essential takeaways", "Reinforce the three ideas worth remembering."),
        ("NEXT", "Continue the lesson", "Connect this concept to the next module."),
    ),
}


def _scene_layer(
    layer: MotionLayer,
    *,
    start_ms: int,
    end_ms: int,
    scene_index: int,
    scene_name: str,
) -> MotionLayer:
    layer.in_ms = max(0, int(start_ms))
    layer.out_ms = max(layer.in_ms + 1, int(end_ms))
    layer.metadata.update(
        {
            "scene_index": int(scene_index),
            "scene_name": str(scene_name),
            "production_template_scene": True,
        }
    )
    return layer


def _build_production_storyboard(
    template_id: str,
    width: int,
    height: int,
    controls: Mapping[str, Any],
) -> list[MotionLayer]:
    scenes = _PRODUCTION_STORYBOARDS[template_id]
    duration = int(controls["duration_ms"])
    accent = str(controls["accent_color"])
    surface = str(controls["surface_color"])
    headline = str(controls["headline"])
    subtitle = str(controls["subtitle"])
    cta = str(controls.get("cta") or "LEARN MORE")
    landscape = width >= height
    title_size = max(40.0, min(width, height) * (.074 if landscape else .062))
    layers: list[MotionLayer] = [
        _shape(
            "Template Background",
            width,
            height,
            width * .5,
            height * .5,
            surface,
            duration,
            role="background",
        )
    ]
    progress = _shape(
        "Story Progress",
        width * .86,
        max(5.0, height * .006),
        width * .5,
        height * .94,
        accent,
        duration,
        role="progress",
    )
    progress.transform.scale = _keyframed(
        [.03, 1.0],
        "vector2",
        [
            (0, [.03, 1.0], "linear"),
            (duration, [1.0, 1.0], "linear"),
        ],
    )
    layers.append(progress)
    scene_count = len(scenes)
    for index, (kicker, scene_title, body) in enumerate(scenes):
        start = int(round(duration * index / scene_count))
        end = int(round(duration * (index + 1) / scene_count))
        local_duration = max(1, end - start)
        if index == 0:
            scene_title = headline
            body = subtitle
        elif index == scene_count - 1:
            body = f"{body}  {cta}"
        group = MotionLayer(
            name=f"Scene {index + 1:02d} - {kicker}",
            layer_type="group",
            in_ms=start,
            out_ms=end,
            metadata={
                "template_role": "scene",
                "scene_index": index + 1,
                "scene_name": kicker,
                "production_template_scene": True,
            },
        )
        layers.append(group)

        if template_id in {
            "ios_app_ui_motion_kit",
            "mobile_onboarding_flow",
            "responsive_saas_product_tour",
        }:
            shell_width = width * (.44 if landscape else .82)
            shell_height = height * (.76 if landscape else .58)
            shell_x = width * (.69 if landscape else .5)
            shell_y = height * (.51 if landscape else .62)
            text_x = width * (.23 if landscape else .5)
            text_y = height * (.30 if landscape else .15)
            align = "left" if landscape else "center"
            shell = _shape(
                f"Scene {index + 1} App Surface",
                shell_width,
                shell_height,
                shell_x,
                shell_y,
                "#F4F6F8",
                local_duration,
                role="ui_screen",
            )
            shell.source.params["radius"] = min(width, height) * .025
            status = _shape(
                f"Scene {index + 1} Status Bar",
                shell_width * .88,
                shell_height * .028,
                shell_x,
                shell_y - shell_height * .455,
                "#B7C0CA",
                local_duration,
                role="status_bar",
            )
            nav = _shape(
                f"Scene {index + 1} Navigation",
                shell_width * .88,
                shell_height * .09,
                shell_x,
                shell_y - shell_height * .40,
                "#DCE2E8",
                local_duration,
                role="navigation",
            )
            card = _shape(
                f"Scene {index + 1} Feature Card",
                shell_width * .78,
                shell_height * .25,
                shell_x,
                shell_y - shell_height * .12,
                f"{accent[:7]}CC",
                local_duration,
                role="media_slot",
            )
            card.source.params["radius"] = min(width, height) * .018
            children = [shell, status, nav, card]
            if index == 0:
                for tile_index in range(3):
                    tile = _shape(
                        f"Scene {index + 1} Quick Action {tile_index + 1}",
                        shell_width * .22,
                        shell_height * .095,
                        shell_x + shell_width * (-.26 + tile_index * .26),
                        shell_y + shell_height * .16,
                        "#D9DEE4" if tile_index != 1 else f"{accent[:7]}88",
                        local_duration,
                        role="quick_action",
                    )
                    tile.source.params["radius"] = min(width, height) * .012
                    children.append(tile)
                children.append(
                    _shape(
                        f"Scene {index + 1} Tab Bar",
                        shell_width * .84,
                        shell_height * .075,
                        shell_x,
                        shell_y + shell_height * .405,
                        "#D1D7DE",
                        local_duration,
                        role="tab_bar",
                    )
                )
            elif index == 1:
                search = _shape(
                    f"Scene {index + 1} Search Field",
                    shell_width * .76,
                    shell_height * .075,
                    shell_x,
                    shell_y - shell_height * .24,
                    "#DCE2E8",
                    local_duration,
                    role="search_field",
                )
                search.source.params["radius"] = min(width, height) * .014
                children.append(search)
                for row_index in range(3):
                    children.append(
                        _shape(
                            f"Scene {index + 1} Result Row {row_index + 1}",
                            shell_width * .76,
                            shell_height * .08,
                            shell_x,
                            shell_y + shell_height * (.11 + row_index * .105),
                            "#E7EAEE" if row_index % 2 else "#D9DEE4",
                            local_duration,
                            role="list_row",
                        )
                    )
            elif index == 2:
                progress_ring = _shape(
                    f"Scene {index + 1} Progress Ring",
                    shell_width * .18,
                    shell_width * .18,
                    shell_x - shell_width * .24,
                    shell_y + shell_height * .19,
                    f"{accent[:7]}CC",
                    local_duration,
                    shape="ellipse",
                    role="progress_control",
                )
                toggle_track = _shape(
                    f"Scene {index + 1} Toggle Track",
                    shell_width * .16,
                    shell_height * .065,
                    shell_x + shell_width * .24,
                    shell_y + shell_height * .18,
                    f"{accent[:7]}CC",
                    local_duration,
                    role="toggle",
                )
                toggle_track.source.params["radius"] = min(width, height) * .03
                toggle_knob = _shape(
                    f"Scene {index + 1} Toggle Knob",
                    shell_height * .048,
                    shell_height * .048,
                    shell_x + shell_width * .285,
                    shell_y + shell_height * .18,
                    "#FFFFFF",
                    local_duration,
                    shape="ellipse",
                    role="toggle_knob",
                )
                children.extend([progress_ring, toggle_track, toggle_knob])
            elif index == 3:
                notification = _shape(
                    f"Scene {index + 1} Notification",
                    shell_width * .74,
                    shell_height * .12,
                    shell_x,
                    shell_y - shell_height * .28,
                    "#FFFFFF",
                    local_duration,
                    role="notification",
                )
                notification.source.params["radius"] = min(width, height) * .018
                sheet = _shape(
                    f"Scene {index + 1} Bottom Sheet",
                    shell_width * .88,
                    shell_height * .38,
                    shell_x,
                    shell_y + shell_height * .29,
                    "#E5E9EE",
                    local_duration,
                    role="bottom_sheet",
                )
                sheet.source.params["radius"] = min(width, height) * .025
                handle = _shape(
                    f"Scene {index + 1} Sheet Handle",
                    shell_width * .14,
                    shell_height * .014,
                    shell_x,
                    shell_y + shell_height * .12,
                    "#9DA7B2",
                    local_duration,
                    role="sheet_handle",
                )
                children.extend([notification, sheet, handle])
            else:
                success = _shape(
                    f"Scene {index + 1} Success",
                    shell_width * .20,
                    shell_width * .20,
                    shell_x,
                    shell_y + shell_height * .11,
                    f"{accent[:7]}CC",
                    local_duration,
                    shape="ellipse",
                    role="success_state",
                )
                action = _shape(
                    f"Scene {index + 1} Primary Action",
                    shell_width * .62,
                    shell_height * .09,
                    shell_x,
                    shell_y + shell_height * .34,
                    accent,
                    local_duration,
                    role="cta_button",
                )
                action.source.params["radius"] = min(width, height) * .016
                children.extend([success, action])
        else:
            text_x = width * (.23 if landscape else .5)
            text_y = height * (.26 if landscape else .18)
            align = "left" if landscape else "center"
            media_width = width * (.52 if landscape else .86)
            media_height = height * (.64 if landscape else .43)
            media_x = width * (.68 if landscape else .5)
            media_y = height * (.53 if landscape else .62)
            media = _shape(
                f"Scene {index + 1} Media",
                media_width,
                media_height,
                media_x,
                media_y,
                "#27313D",
                local_duration,
                role="media_slot",
            )
            media.source.params.update(
                {
                    "stroke": f"{accent[:7]}99",
                    "stroke_width": max(2.0, min(width, height) * .004),
                    "radius": min(width, height) * .018,
                }
            )
            proof = _shape(
                f"Scene {index + 1} Proof Card",
                media_width * (.46 if index % 2 == 0 else .62),
                media_height * .22,
                media_x + media_width * (.22 if index % 2 == 0 else -.13),
                media_y + media_height * (.31 if index % 3 else -.31),
                f"{accent[:7]}DD",
                local_duration,
                role="proof_card",
            )
            proof.source.params["radius"] = min(width, height) * .014
            children = [media, proof]
            if template_id in {
                "course_module_opener_20s",
                "step_by_step_tutorial_45s",
                "lesson_explainer_60s",
            }:
                marker = _shape(
                    f"Scene {index + 1} Chapter Marker",
                    max(44.0, min(width, height) * .075),
                    max(44.0, min(width, height) * .075),
                    media_x - media_width * .39,
                    media_y - media_height * .37,
                    accent,
                    local_duration,
                    shape="ellipse",
                    role="chapter_marker",
                )
                children.append(marker)
                if index in {1, 4, 6}:
                    for item_index in range(3):
                        item = _shape(
                            f"Scene {index + 1} Learning Item {item_index + 1}",
                            media_width * .32,
                            media_height * .09,
                            media_x + media_width * .22,
                            media_y + media_height * (-.15 + item_index * .14),
                            "#465362" if item_index % 2 else "#536274",
                            local_duration,
                            role="learning_item",
                        )
                        item.source.params["radius"] = min(width, height) * .01
                        children.append(item)
            elif index == 2:
                for benefit_index in range(3):
                    benefit = _shape(
                        f"Scene {index + 1} Benefit {benefit_index + 1}",
                        media_width * .22,
                        media_height * .17,
                        media_x + media_width * (-.27 + benefit_index * .27),
                        media_y + media_height * .13,
                        "#3A4654" if benefit_index != 1 else f"{accent[:7]}AA",
                        local_duration,
                        role="benefit_card",
                    )
                    benefit.source.params["radius"] = min(width, height) * .012
                    children.append(benefit)

        kicker_layer = _text(
            f"Scene {index + 1} Kicker",
            kicker,
            text_x,
            text_y - title_size * 1.05,
            title_size * .26,
            accent,
            local_duration,
            role="scene_kicker",
            align=align,
        )
        title_layer = _text(
            f"Scene {index + 1} Headline",
            scene_title,
            text_x,
            text_y,
            title_size * (.76 if landscape else .66),
            "#FFFFFF",
            local_duration,
            role="headline",
            align=align,
        )
        body_layer = _text(
            f"Scene {index + 1} Body",
            body,
            text_x,
            text_y + title_size * 1.15,
            title_size * .28,
            "#C4CDD7",
            local_duration,
            role="subtitle",
            align=align,
        )
        text_width = width * (.39 if landscape else .86)
        for text_layer in (kicker_layer, title_layer, body_layer):
            text_layer.source.params["width"] = text_width
        children.extend([kicker_layer, title_layer, body_layer])
        for child in children:
            child.parent_id = group.id
            child.behaviors.append(
                _behavior(
                    "slide",
                    local_duration,
                    direction="in",
                    distance=[0, max(18.0, height * .035)],
                    hold_after=True,
                )
            )
            _scene_layer(
                child,
                start_ms=start,
                end_ms=end,
                scene_index=index + 1,
                scene_name=kicker,
            )
            layers.append(child)
    return layers


def _build_layers(template_id: str, width: int, height: int, controls: Mapping[str, Any]) -> list[MotionLayer]:
    duration = int(controls["duration_ms"])
    headline, subtitle = controls["headline"], controls["subtitle"]
    accent, surface = controls["accent_color"], controls["surface_color"]
    landscape = width >= height
    safe_x, safe_y = width * .07, height * .08
    title_size = max(42.0, min(width, height) * (.09 if landscape else .075))
    layers: list[MotionLayer] = []
    if template_id in _PRODUCTION_STORYBOARDS:
        return _build_production_storyboard(
            template_id,
            width,
            height,
            controls,
        )
    if template_id == "learn_keyframes_graph":
        background = _shape("Tutorial Background", width, height, width * .5, height * .5,
                            surface, duration, role="background")
        card = _shape("Focus Card", width * .22, height * .28, width * .22, height * .55,
                      accent, duration, role="keyframe_subject")
        card.transform.position = _keyframed(
            [width * .22, height * .55],
            "vector2",
            [
                (0, [width * .22, height * .55], "bezier"),
                (duration // 2, [width * .5, height * .35], "bezier"),
                (duration, [width * .78, height * .55], "bezier"),
            ],
        )
        card.transform.rotation = _keyframed(
            -8.0, "scalar",
            [(0, -8.0, "bezier"), (duration // 2, 7.0, "bezier"), (duration, 0.0, "bezier")],
        )
        card.transform.scale = _keyframed(
            [.82, .82], "vector2",
            [(0, [.82, .82], "bezier"), (duration // 2, [1.14, 1.14], "bezier"),
             (duration, [1.0, 1.0], "bezier")],
        )
        card.metadata["motion_blur"] = {"enabled": True, "samples": 8, "shutter": .65}
        layers.extend([
            background,
            card,
            _text("Tutorial Headline", headline, width * .5, height * .16, title_size * .72,
                  "#ffffff", duration, role="headline", align="center"),
            _text("Step Hint", "SELECT FOCUS CARD - OPEN GRAPH EDITOR", width * .5,
                  height * .86, title_size * .24, "#b8c1cc", duration, role="tutorial_hint",
                  align="center"),
        ])
    elif template_id == "learn_typography_vector":
        background = _shape("Tutorial Background", width, height, width * .5, height * .5,
                            surface, duration, role="background")
        headline_layer = _text(
            "Tutorial Headline", headline, width * .5, height * .42, title_size,
            "#ffffff", duration, role="headline", align="center",
        )
        headline_layer.source.params["text_animation"].update({
            "in": "slide-up-in", "unit": "word", "stagger_ms": 90,
        })
        accent_path = MotionLayer(
            name="Drawn Accent",
            layer_type="shape",
            out_ms=duration,
            source=SourceRef(kind="shape", params={
                "shape": "path",
                "width": width * .58,
                "height": height * .18,
                "fill": "#00000000",
                "stroke": accent,
                "stroke_width": max(5.0, min(width, height) * .009),
                "trim": {"start": 0.0, "end": .82, "offset": 0.0},
            }),
            metadata={"template_role": "vector_path"},
        )
        accent_path.transform.position.default = [width * .5, height * .62]
        accent_path.behaviors.append(_behavior("draw_on", duration, hold_after=True))
        layers.extend([
            background,
            accent_path,
            headline_layer,
            _text("Step Hint", "EDIT WORD STAGGER - THEN MOVE PATH HANDLES", width * .5,
                  height * .82, title_size * .23, "#b8c1cc", duration,
                  role="tutorial_hint", align="center"),
        ])
    elif template_id == "learn_particles_composite":
        background = _shape("Tutorial Background", width, height, width * .5, height * .5,
                            surface, duration, role="background")
        glow = _shape("Glow Disc", min(width, height) * .38, min(width, height) * .38,
                      width * .5, height * .48, f"{accent[:7]}66", duration,
                      shape="ellipse", role="blend_subject")
        glow.blend_mode = "screen"
        glow.behaviors.append(_behavior("pulse", duration, amount=.14, hold_after=True))
        particles = create_particle_layer(width=width, height=height, duration_ms=duration, params={
            "seed": 1403,
            "birth_rate": 18,
            "max_particles": 420,
            "bursts": [{"time_ms": 180, "count": 72}, {"time_ms": duration // 2, "count": 36}],
            "particle": {
                "shape": "triangle", "size_start": 34, "size_end": 5,
                "opacity_start": 1, "opacity_end": 0, "color_start": "#ffffff",
                "color_end": f"{accent[:7]}00", "rotation_speed": 150, "sprite_uri": "",
            },
        })
        particles.name = "Tutorial Particles"
        particles.metadata["template_role"] = "particles"
        particles.blend_mode = "screen"
        layers.extend([
            background,
            glow,
            particles,
            _text("Tutorial Headline", headline, width * .5, height * .48, title_size * .84,
                  "#ffffff", duration, role="headline", align="center"),
            _text("Step Hint", "CHANGE BURST COUNT - COMPARE SCREEN / NORMAL", width * .5,
                  height * .82, title_size * .23, "#cbd4dd", duration,
                  role="tutorial_hint", align="center"),
        ])
    elif template_id == "learn_interactive_unreal_button":
        from app.motion_designer.interactive_button import ButtonAction, create_button_component

        background = _shape("Tutorial Background", width, height, width * .5, height * .5,
                            surface, duration, role="background")
        group = MotionLayer(
            name="CTA Button",
            layer_type="group",
            out_ms=duration,
            metadata={"template_role": "interactive_button", "umg_export": "button"},
        )
        component = create_button_component(group)
        component.transition_duration_ms = 180
        component.easing = "spring"
        component.actions["clicked"] = [
            ButtonAction(action_type="emit_event", name="tutorial_cta_clicked"),
            ButtonAction(action_type="play_animation", name="cta_confirm"),
        ]
        group.metadata["interactive_component"] = component.to_dict()
        plate = _shape("Button Surface", width * (.34 if landscape else .68), height * .15,
                       width * .5, height * .52, accent, duration, role="button_surface")
        plate.parent_id = group.id
        label = _text("Button Label", "START CREATING", width * .5, height * .52,
                      title_size * .42, "#07110f", duration, role="button_label", align="center")
        label.parent_id = group.id
        layers.extend([
            background,
            group,
            plate,
            label,
            _text("Tutorial Headline", headline, width * .5, height * .24, title_size * .72,
                  "#ffffff", duration, role="headline", align="center"),
            _text("Step Hint", "HOVER + PRESS - THEN OPEN BUTTON AND UNREAL LINK", width * .5,
                  height * .78, title_size * .22, "#b8c1cc", duration,
                  role="tutorial_hint", align="center"),
        ])
    elif template_id == "learn_generators_replicators":
        from app.motion_designer.generators import create_generator_layer

        background = create_generator_layer(
            "gradient", width=width, height=height, duration_ms=duration,
            name="Procedural Gradient",
        )
        background.source.params.update({
            "color_a": accent,
            "color_b": surface,
            "angle": 28.0,
        })
        background.metadata["template_role"] = "generator"
        star = _shape(
            "Replicated Star",
            min(width, height) * .09,
            min(width, height) * .09,
            width * .5,
            height * .5,
            "#f2c14e",
            duration,
            shape="star",
            role="replicator",
        )
        star.source.params.update({
            "sides": 5,
            "inner_ratio": .45,
            "stroke": "#fff2c5",
            "stroke_width": 3,
        })
        star.metadata["replicator"] = {
            "enabled": True,
            "arrangement": "radial",
            "count": 12,
            "columns": 4,
            "offset": [min(width, height) * .29, 0.0],
            "rotation": 15.0,
            "scale": [.96, .96],
            "opacity_start": 1.0,
            "opacity_end": .55,
            "jitter": [0.0, 0.0],
            "seed": 0,
        }
        layers.extend([
            background,
            star,
            _text("Tutorial Headline", headline, width * .5, height * .5,
                  title_size * .72, "#ffffff", duration, role="headline", align="center"),
            _text("Step Hint", "CHANGE GENERATOR - THEN LINE / GRID / RADIAL",
                  width * .5, height * .84, title_size * .22, "#cbd4dd",
                  duration, role="tutorial_hint", align="center"),
        ])
    elif template_id in {"clean_lower_third", "character_nameplate"}:
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
                                  variant: str = "", controls: Mapping[str, Any] | None = None,
                                  replace_existing: bool = True) -> MotionComposition:
    template = get_template(template_id)
    chosen_variant = str(variant or recommended_variant(composition.width, composition.height))
    if chosen_variant not in template.variants:
        raise ValueError(f"template {template.id} does not support variant {chosen_variant}")
    values = _controls(template, controls)
    candidate = MotionComposition.from_dict(composition.to_dict())
    previous_state = candidate.metadata.get("last_applied_template")
    previous_state = previous_state if isinstance(previous_state, dict) else {}
    previous_instance_id = str(previous_state.get("template_instance_id") or "")
    removed_layer_ids: list[str] = []
    if replace_existing and previous_instance_id:
        removed_layer_ids = [
            layer.id
            for layer in candidate.layers
            if str(layer.metadata.get("template_instance_id") or "")
            == previous_instance_id
        ]
        removed = set(removed_layer_ids)
        candidate.layers = [
            layer
            for layer in candidate.layers
            if layer.id not in removed and layer.parent_id not in removed
        ]
    layers = _build_layers(template.id, candidate.width, candidate.height, values)
    instance_id = new_motion_id("template_instance")
    id_map = {layer.id: new_motion_id("layer") for layer in layers}
    for index, layer in enumerate(layers):
        previous_id = layer.id
        layer.id = id_map[previous_id]
        if layer.parent_id:
            layer.parent_id = id_map.get(layer.parent_id, layer.parent_id)
        layer.metadata.update({
            "template_id": template.id,
            "template_instance_id": instance_id,
            "template_variant": chosen_variant,
        })
        if template.tutorial_steps:
            step_index = min(index, len(template.tutorial_steps) - 1)
            layer.metadata.update({
                "tutorial_template": template.id,
                "tutorial_step": step_index + 1,
                "tutorial_note": template.tutorial_steps[step_index],
            })
    candidate.layers.extend(layers)
    if not candidate.layers[: -len(layers)]:
        candidate.duration_ms = int(values["duration_ms"])
    else:
        candidate.duration_ms = max(
            int(candidate.duration_ms),
            int(values["duration_ms"]),
        )
    candidate.metadata["last_applied_template"] = {
        "schema": TEMPLATE_SCHEMA, "template_id": template.id,
        "template_instance_id": instance_id, "variant": chosen_variant,
        "published_controls": deepcopy(values), "realtime_grade": template.realtime_grade,
        "description": template.description,
        "features": list(template.features),
        "tutorial_steps": list(template.tutorial_steps),
        "scene_count": template.scene_count,
        "workflow": template.workflow,
        "replace_items": list(template.replace_items),
        "tags": list(template.tags),
        "replaced_layer_ids": removed_layer_ids,
    }
    if template.tutorial_steps:
        candidate.metadata["motion_tutorial"] = {
            "schema": "tigercapture.motion.tutorial.v1",
            "template_id": template.id,
            "template_instance_id": instance_id,
            "title": template.name,
            "description": template.description,
            "features": list(template.features),
            "steps": [
                {"index": index + 1, "instruction": instruction, "complete": False}
                for index, instruction in enumerate(template.tutorial_steps)
            ],
            "current_step": 1,
            "difficulty": template.difficulty,
            "estimated_minutes": template.estimated_minutes,
        }
    else:
        candidate.metadata.pop("motion_tutorial", None)
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
