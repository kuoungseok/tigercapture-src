"""Action adapter for Motion Designer story and platform direction."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.motion_designer.schema import MotionComposition
from app.motion_designer.story_direction import (
    add_story_beat,
    apply_platform_variant,
    bind_story_audio,
    inspect_story,
    plan_platform_variant,
    preflight_platform,
    preflight_story,
    preview_platform_variant,
    reorder_story_beat,
    update_story,
    update_story_beat,
)


class MotionStoryAdapterMixin:
    def _motion_story_changed(
        self,
        composition: MotionComposition,
        undo_label: str,
        **payload: Any,
    ) -> dict[str, Any]:
        composition.revision += 1
        self._motion_sync_owner()
        return {
            "changed": True,
            "undo_label": undo_label,
            "composition_id": composition.id,
            "revision": composition.revision,
            **payload,
        }

    def motion_story_inspect(self, *, composition_id: str) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        return {
            "story": inspect_story(composition),
            "preflight": preflight_story(composition),
        }

    def motion_story_update(
        self,
        *,
        composition_id: str,
        changes: Mapping[str, Any],
    ) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        story = update_story(composition, changes)
        return self._motion_story_changed(
            composition,
            "Update Story Direction",
            story=story,
        )

    def motion_story_beat_add(
        self,
        *,
        composition_id: str,
        role: str,
        start_ms: int,
        end_ms: int,
        purpose: str = "",
        emotion: str = "",
        character: str = "",
        copy: str = "",
        visual: str = "",
        audio_cue: str = "",
        scene_id: str = "",
        layer_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        beat = add_story_beat(
            composition,
            role=role,
            start_ms=start_ms,
            end_ms=end_ms,
            purpose=purpose,
            emotion=emotion,
            character=character,
            copy=copy,
            visual=visual,
            audio_cue=audio_cue,
            scene_id=scene_id,
            layer_ids=layer_ids or (),
        )
        return self._motion_story_changed(
            composition,
            "Add Story Beat",
            beat=beat,
        )

    def motion_story_beat_update(
        self,
        *,
        composition_id: str,
        beat_id: str,
        changes: Mapping[str, Any],
    ) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        beat = update_story_beat(composition, beat_id, changes)
        return self._motion_story_changed(
            composition,
            "Update Story Beat",
            beat=beat,
        )

    def motion_story_beat_reorder(
        self,
        *,
        composition_id: str,
        beat_id: str,
        order: int,
    ) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        beats = reorder_story_beat(composition, beat_id, order)
        return self._motion_story_changed(
            composition,
            "Reorder Story Beat",
            beats=beats,
        )

    def motion_story_audio_bind(
        self,
        *,
        composition_id: str,
        beat_id: str,
        source_kind: str,
        source_id: str,
        cue_ms: int,
        label: str = "",
        tempo_bpm: float | None = None,
    ) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        binding = bind_story_audio(
            composition,
            beat_id=beat_id,
            source_kind=source_kind,
            source_id=source_id,
            cue_ms=cue_ms,
            label=label,
            tempo_bpm=tempo_bpm,
        )
        return self._motion_story_changed(
            composition,
            "Bind Story Audio",
            binding=binding,
        )

    def motion_platform_variant_plan(
        self,
        *,
        composition_id: str,
        platform: str,
    ) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        return {"plan": plan_platform_variant(composition, platform)}

    def motion_platform_variant_preview(
        self,
        *,
        composition_id: str,
        platform: str,
    ) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        return preview_platform_variant(composition, platform)

    def motion_platform_variant_apply(
        self,
        *,
        composition_id: str,
        plan: Mapping[str, Any],
        approved: bool = False,
    ) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        candidate = apply_platform_variant(composition, plan, approved=approved)
        self._motion_store()[candidate.id] = candidate
        self._motion_sync_owner()
        return {
            "changed": True,
            "undo_label": "Create Platform Variant",
            "source_composition_id": composition.id,
            "source_revision": composition.revision,
            "composition": candidate.to_dict(),
            "preflight": preflight_platform(
                candidate,
                platform=str(plan.get("platform") or ""),
            ),
        }

    def motion_platform_preflight(
        self,
        *,
        composition_id: str,
        platform: str,
    ) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        return {
            "story": preflight_story(composition),
            "platform": preflight_platform(composition, platform=platform),
        }


__all__ = ["MotionStoryAdapterMixin"]
