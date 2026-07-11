"""One-click character timeline templates.

This module is intentionally Qt-free.  It turns one Character Asset Hub record
plus a template id into a small, executable Action Registry plan.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from app.character_asset_hub import build_character_asset_timeline_add


CHARACTER_ONE_CLICK_TEMPLATE_SCHEMA = "tigercapture.character_one_click_template.v1"
CHARACTER_ONE_CLICK_PLAN_SCHEMA = "tigercapture.character_one_click_plan.v1"


@dataclass(frozen=True)
class CharacterOneClickTemplate:
    id: str
    name: str
    description: str
    duration_ms: int
    preferred_kinds: tuple[str, ...]
    tags: tuple[str, ...]
    title: str
    caption: str
    actor_scale: float = 1.0
    actor_pos_x: float = 0.5
    actor_pos_y: float = 0.5
    text_y: float = 0.16
    fallback_sequence: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": CHARACTER_ONE_CLICK_TEMPLATE_SCHEMA,
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "duration_ms": int(self.duration_ms),
            "preferred_kinds": list(self.preferred_kinds),
            "tags": list(self.tags),
            "title": self.title,
            "caption": self.caption,
            "actor_scale": float(self.actor_scale),
            "actor_pos_x": float(self.actor_pos_x),
            "actor_pos_y": float(self.actor_pos_y),
            "text_y": float(self.text_y),
            "fallback_sequence": [dict(row) for row in self.fallback_sequence],
        }


_TEMPLATES: tuple[CharacterOneClickTemplate, ...] = (
    CharacterOneClickTemplate(
        id="template-character-intro-short",
        name="Character intro short",
        description="A fast identity card: character reveal, nameplate, caption, and clean web polish.",
        duration_ms=5200,
        preferred_kinds=("live2d", "spine", "mmd", "vrm"),
        tags=("character", "intro", "short", "character-short", "one-click"),
        title="CHARACTER INTRO",
        caption="Meet the character",
        actor_scale=0.92,
        actor_pos_y=0.58,
        text_y=0.14,
        fallback_sequence=(
            {"kind": "actor", "preset_id": "actor-live2d-placeholder", "at_ms": 0},
            {"kind": "title", "preset_id": "title-live2d-nameplate", "at_ms": 0},
            {"kind": "effect", "preset_id": "effect-character-focus"},
            {"kind": "caption_style", "preset_id": "caption-clean-subtitle"},
        ),
    ),
    CharacterOneClickTemplate(
        id="template-talking-live2d-short",
        name="Talking Live2D short",
        description="Talking-character short with face-friendly placement, subtitle style, and voice polish.",
        duration_ms=8000,
        preferred_kinds=("live2d", "spine", "vrm"),
        tags=("character", "talking", "live2d", "short", "character-short", "one-click"),
        title="TODAY'S TOPIC",
        caption="Talking character short",
        actor_scale=0.86,
        actor_pos_x=0.68,
        actor_pos_y=0.62,
        text_y=0.78,
        fallback_sequence=(
            {"kind": "actor", "preset_id": "actor-live2d-placeholder", "at_ms": 0},
            {"kind": "title", "preset_id": "title-live2d-nameplate", "at_ms": 0},
            {"kind": "caption_style", "preset_id": "caption-clean-subtitle"},
            {"kind": "audio", "preset_id": "audio-voiceover-bright-web", "condition": "if_audio"},
        ),
    ),
    CharacterOneClickTemplate(
        id="template-game-ui-commentary",
        name="Game UI commentary",
        description="Character commentary over game/UI footage with readable lower captions and punchy overlay.",
        duration_ms=7000,
        preferred_kinds=("live2d", "spine", "vrm"),
        tags=("character", "game", "commentary", "ui", "short", "character-short", "one-click"),
        title="GAME COMMENTARY",
        caption="Quick reaction",
        actor_scale=0.64,
        actor_pos_x=0.78,
        actor_pos_y=0.69,
        text_y=0.84,
        fallback_sequence=(
            {"kind": "actor", "preset_id": "actor-live2d-placeholder", "at_ms": 0},
            {"kind": "effect", "preset_id": "effect-vtuber-overlay-pop", "condition": "if_video"},
            {"kind": "caption_style", "preset_id": "caption-clean-subtitle"},
            {"kind": "audio", "preset_id": "audio-streamer-voice", "condition": "if_audio"},
        ),
    ),
    CharacterOneClickTemplate(
        id="template-gacha-character-showcase",
        name="Gacha character showcase",
        description="Hero-card showcase for a character pull, reveal, or outfit presentation.",
        duration_ms=6200,
        preferred_kinds=("live2d", "spine", "mmd", "vrm"),
        tags=("character", "gacha", "showcase", "anime", "short", "character-short", "one-click"),
        title="NEW CHARACTER",
        caption="Showcase",
        actor_scale=0.98,
        actor_pos_y=0.57,
        text_y=0.12,
        fallback_sequence=(
            {"kind": "actor", "preset_id": "actor-spine-placeholder", "at_ms": 0},
            {"kind": "effect", "preset_id": "effect-anime-cleanline"},
            {"kind": "title", "preset_id": "title-live2d-nameplate", "at_ms": 0},
            {"kind": "caption_style", "preset_id": "caption-meme-punch"},
        ),
    ),
    CharacterOneClickTemplate(
        id="template-mmd-dance-clip",
        name="MMD dance clip",
        description="MMD-focused dance starter with motion, beat title, impact transition, and web loudness.",
        duration_ms=15000,
        preferred_kinds=("mmd",),
        tags=("character", "mmd", "dance", "music", "one-click"),
        title="DANCE CLIP",
        caption="MMD dance",
        actor_scale=0.9,
        actor_pos_y=0.61,
        text_y=0.13,
        fallback_sequence=(
            {"kind": "actor", "preset_id": "actor-spine-placeholder", "at_ms": 0},
            {"kind": "title", "preset_id": "title-score-callout", "at_ms": 180},
            {"kind": "motion", "preset_id": "motion-shake-impact", "at_ms": 580},
            {"kind": "transition", "preset_id": "transition-hit-white"},
            {"kind": "audio", "preset_id": "audio-music-master-web", "condition": "if_audio"},
        ),
    ),
    CharacterOneClickTemplate(
        id="template-anime-pv-intro",
        name="Anime PV intro",
        description="Anime preview intro with clean-line character focus, title hit, and short-form polish.",
        duration_ms=7200,
        preferred_kinds=("live2d", "spine", "mmd", "vrm"),
        tags=("character", "anime", "pv", "intro", "one-click"),
        title="ANIME PV",
        caption="Opening cut",
        actor_scale=0.94,
        actor_pos_y=0.59,
        text_y=0.18,
        fallback_sequence=(
            {"kind": "actor", "preset_id": "actor-spine-placeholder", "at_ms": 0},
            {"kind": "effect", "preset_id": "effect-anime-cleanline"},
            {"kind": "title", "preset_id": "title-live2d-nameplate", "at_ms": 0},
            {"kind": "transition", "preset_id": "transition-hit-white"},
        ),
    ),
    CharacterOneClickTemplate(
        id="template-meme-reaction-character",
        name="Meme reaction",
        description="Reaction meme starter with punch caption, character emphasis, and streamer voice chain.",
        duration_ms=5000,
        preferred_kinds=("live2d", "spine", "vrm"),
        tags=("character", "meme", "reaction", "short", "character-short", "one-click"),
        title="NO WAY",
        caption="Reaction",
        actor_scale=0.82,
        actor_pos_x=0.7,
        actor_pos_y=0.63,
        text_y=0.2,
        fallback_sequence=(
            {"kind": "actor", "preset_id": "actor-live2d-placeholder", "at_ms": 0},
            {"kind": "effect", "preset_id": "effect-meme-punch"},
            {"kind": "caption_style", "preset_id": "caption-meme-punch"},
            {"kind": "audio", "preset_id": "audio-streamer-voice", "condition": "if_audio"},
        ),
    ),
    CharacterOneClickTemplate(
        id="template-vtuber-announcement",
        name="VTuber announcement",
        description="VTuber announcement card with avatar target support, nameplate, and social CTA.",
        duration_ms=9000,
        preferred_kinds=("vrm", "live2d", "spine"),
        tags=("character", "vtuber", "announcement", "broadcast", "one-click"),
        title="ANNOUNCEMENT",
        caption="VTuber update",
        actor_scale=0.82,
        actor_pos_x=0.68,
        actor_pos_y=0.62,
        text_y=0.18,
        fallback_sequence=(
            {"kind": "actor", "preset_id": "actor-live2d-placeholder", "at_ms": 0},
            {"kind": "title", "preset_id": "title-live2d-nameplate", "at_ms": 0},
            {"kind": "caption_style", "preset_id": "caption-capcut-word-pop", "at_ms": 200},
            {"kind": "sticker", "preset_id": "sticker-social-cta-burst", "at_ms": 1800},
            {"kind": "audio", "preset_id": "audio-capcut-voice-enhance", "condition": "if_audio"},
        ),
    ),
    CharacterOneClickTemplate(
        id="template-subtitle-to-voice-dialogue-scene",
        name="Subtitle-to-voice dialogue scene",
        description="Character dialogue scene that can synthesize project subtitles to a dialogue audio track.",
        duration_ms=12000,
        preferred_kinds=("live2d", "spine", "vrm"),
        tags=("character", "subtitle", "voice", "dialogue", "tts", "one-click"),
        title="DIALOGUE SCENE",
        caption="Subtitle to voice",
        actor_scale=0.84,
        actor_pos_x=0.66,
        actor_pos_y=0.62,
        text_y=0.8,
        fallback_sequence=(
            {"kind": "actor", "preset_id": "actor-live2d-placeholder", "at_ms": 0},
            {"kind": "caption_style", "preset_id": "caption-clean-subtitle"},
            {"kind": "audio", "preset_id": "audio-voiceover-bright-web", "condition": "if_audio"},
        ),
    ),
)


def character_one_click_templates() -> list[dict[str, Any]]:
    return [template.to_dict() for template in _TEMPLATES]


def character_one_click_template_ids() -> list[str]:
    return [template.id for template in _TEMPLATES]


def character_short_template_ids() -> list[str]:
    return [
        template.id
        for template in _TEMPLATES
        if "character-short" in template.tags
    ]


def character_one_click_template_by_id(template_id: str) -> dict[str, Any] | None:
    target = str(template_id or "").strip()
    for template in _TEMPLATES:
        if template.id == target:
            return template.to_dict()
    return None


def build_character_one_click_template_plan(
    template_id: str,
    asset_record: Mapping[str, Any] | None = None,
    *,
    path: str = "",
    kind: str = "",
    start_ms: int = 0,
    duration_ms: int | None = None,
    track_id: int | None = None,
    clip_id: int | None = None,
    include_decorations: bool = True,
) -> dict[str, Any]:
    """Build an executable action plan for one selected character asset."""
    template = _template_obj(template_id)
    record = _normalized_asset_record(asset_record, path=path, kind=kind)
    asset_kind = str(record.get("kind") or "").casefold()
    start = max(0, _as_int(start_ms, 0))
    duration = max(1, _as_int(duration_ms, template.duration_ms))
    warnings: list[str] = []
    if asset_kind and asset_kind not in template.preferred_kinds:
        warnings.append(f"asset_kind_not_preferred:{asset_kind}")
    if not str(record.get("path") or "").strip():
        warnings.append("missing_asset_path")
    steps: list[dict[str, Any]] = []

    primary = _primary_character_step(template, record, start_ms=start, duration_ms=duration)
    if primary:
        steps.append(primary)
    else:
        warnings.append("no_primary_character_action")

    if include_decorations:
        steps.extend(_decoration_steps(template, start_ms=start, track_id=track_id, clip_id=clip_id))

    primary_executable = bool(primary and primary.get("executable", True))
    return {
        "schema": CHARACTER_ONE_CLICK_PLAN_SCHEMA,
        "ok": bool(primary_executable),
        "template": template.to_dict(),
        "asset": {
            "kind": asset_kind,
            "path": str(record.get("path") or ""),
            "display_name": str(record.get("display_name") or Path(str(record.get("path") or "")).stem),
        },
        "start_ms": start,
        "duration_ms": duration,
        "track_id": track_id,
        "clip_id": clip_id,
        "step_count": len(steps),
        "executable_step_count": sum(1 for step in steps if bool(step.get("executable"))),
        "steps": steps,
        "warnings": warnings,
    }


def _template_obj(template_id: str) -> CharacterOneClickTemplate:
    target = str(template_id or "").strip()
    for template in _TEMPLATES:
        if template.id == target:
            return template
    raise ValueError(f"unknown character template: {target}")


def _normalized_asset_record(
    asset_record: Mapping[str, Any] | None,
    *,
    path: str = "",
    kind: str = "",
) -> dict[str, Any]:
    record = dict(asset_record or {})
    if path and not record.get("path"):
        record["path"] = str(path)
    if kind and not record.get("kind"):
        record["kind"] = str(kind)
    if "path" in record:
        try:
            record["path"] = str(Path(str(record["path"])).expanduser().resolve())
        except Exception:
            record["path"] = str(record["path"])
    if record.get("path") and not isinstance(record.get("render"), Mapping):
        asset_kind = str(record.get("kind") or "").casefold()
        if asset_kind in {"live2d", "spine", "mmd"}:
            record["render"] = {
                "capable": Path(str(record.get("path") or "")).is_file(),
                "status": "direct_action_input",
            }
    if str(record.get("kind") or "").casefold() == "vrm" and not isinstance(record.get("profile"), Mapping):
        try:
            from app.vtuber.vrm_profile import inspect_vrm_profile

            record["profile"] = inspect_vrm_profile(str(record.get("path") or ""))
        except Exception:
            record["profile"] = {"ok": False, "vseeface_compatible": False}
    return record


def _primary_character_step(
    template: CharacterOneClickTemplate,
    record: Mapping[str, Any],
    *,
    start_ms: int,
    duration_ms: int,
) -> dict[str, Any] | None:
    timeline_add = build_character_asset_timeline_add(
        record,
        start_ms=start_ms,
        duration_ms=duration_ms,
    )
    action_id = str(timeline_add.get("action") or "")
    params = dict(timeline_add.get("params") or {})
    if not action_id:
        return None
    if action_id == "actor.add":
        params["duration_ms"] = duration_ms
        params["start_ms"] = start_ms
        params["pos_x"] = float(params.get("pos_x", template.actor_pos_x) or template.actor_pos_x)
        params["pos_y"] = float(params.get("pos_y", template.actor_pos_y) or template.actor_pos_y)
        params["scale"] = float(params.get("scale", template.actor_scale) or template.actor_scale)
        if str(params.get("kind") or "") == "spine" and not str(params.get("anim_name") or ""):
            params["anim_name"] = "idle"
    elif action_id == "mmd.actor.add":
        params["duration_ms"] = duration_ms
        params["start_ms"] = start_ms
    elif action_id == "vtuber.vseeface_select_vrm0_avatar":
        params["path"] = str(params.get("path") or record.get("path") or "")
    return {
        "kind": "action",
        "role": "character",
        "label": str(timeline_add.get("label") or template.name),
        "action": action_id,
        "params": params,
        "at_ms": start_ms,
        "optional": False,
        "executable": bool(timeline_add.get("enabled", True)),
        "reason": str(timeline_add.get("reason") or ""),
    }


def _decoration_steps(
    template: CharacterOneClickTemplate,
    *,
    start_ms: int,
    track_id: int | None,
    clip_id: int | None,
) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    can_text = track_id is not None and clip_id is not None
    base_text_params = {
        "track_id": track_id,
        "clip_id": clip_id,
        "start_ms": start_ms,
        "end_ms": start_ms + min(2600, max(1400, template.duration_ms // 3)),
    }
    title_style = {
        "font_size": 64,
        "font_weight": 850,
        "color": "#FFFFFF",
        "outline_color": "#11131C",
        "outline_width": 5,
        "position_x": 0.5,
        "position_y": template.text_y,
        "shadow_color": "#000000",
        "shadow_offset_y": 4,
        "shadow_blur": 8,
    }
    caption_style = {
        "font_size": 42,
        "font_weight": 720,
        "color": "#F7F8FF",
        "outline_color": "#11131C",
        "outline_width": 4,
        "position_x": 0.5,
        "position_y": 0.82,
    }
    steps.append({
        "kind": "action",
        "role": "title",
        "label": "Add template title",
        "action": "text.add",
        "params": {**base_text_params, "text": template.title, "style": title_style, "animation": {"preset_id": "pop-in", "in_animation": "pop-in", "out_animation": "fade-out"}},
        "at_ms": start_ms,
        "optional": True,
        "executable": bool(can_text),
        "reason": "" if can_text else "requires_video_track_and_clip",
    })
    steps.append({
        "kind": "action",
        "role": "caption",
        "label": "Add template caption",
        "action": "text.add",
        "params": {
            **base_text_params,
            "start_ms": start_ms + 600,
            "end_ms": start_ms + min(template.duration_ms, 4200),
            "text": template.caption,
            "style": caption_style,
            "animation": {"preset_id": "slide-up", "in_animation": "slide-up-in", "out_animation": "fade-out"},
        },
        "at_ms": start_ms + 600,
        "optional": True,
        "executable": bool(can_text),
        "reason": "" if can_text else "requires_video_track_and_clip",
    })
    if template.id == "template-subtitle-to-voice-dialogue-scene":
        steps.append({
            "kind": "action",
            "role": "tts",
            "label": "Generate subtitle dialogue voice",
            "action": "tts.subtitle.generate_to_timeline",
            "params": {"voice": "", "model_name": "", "track_name": "Dialogue"},
            "at_ms": start_ms,
            "optional": True,
            "executable": True,
            "reason": "requires_project_subtitles_and_tts_sidecar",
        })
    return steps


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


__all__ = [
    "CHARACTER_ONE_CLICK_PLAN_SCHEMA",
    "CHARACTER_ONE_CLICK_TEMPLATE_SCHEMA",
    "build_character_one_click_template_plan",
    "character_one_click_template_by_id",
    "character_one_click_template_ids",
    "character_short_template_ids",
    "character_one_click_templates",
]
