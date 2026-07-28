"""Action adapter for reviewable Motion AI style and story direction."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.motion_designer.style_director import (
    apply_story_direction,
    apply_style_candidate,
    plan_story_direction,
    plan_style_direction,
    set_style_lock,
    trend_preflight,
)


class MotionStyleDirectorAdapterMixin:
    def motion_ai_style_plan(
        self,
        *,
        composition_id: str,
        prompt: str,
        references: list[Mapping[str, Any]] | None = None,
        layer_ids: list[str] | None = None,
        seed: int = 20260729,
    ) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        return plan_style_direction(
            composition,
            prompt,
            references or (),
            layer_ids=layer_ids or (),
            seed=seed,
        )

    def motion_ai_style_candidates_generate(
        self,
        *,
        composition_id: str,
        prompt: str,
        references: list[Mapping[str, Any]] | None = None,
        layer_ids: list[str] | None = None,
        seed: int = 20260729,
    ) -> dict[str, Any]:
        plan = self.motion_ai_style_plan(
            composition_id=composition_id,
            prompt=prompt,
            references=references,
            layer_ids=layer_ids,
            seed=seed,
        )
        return {
            "plan": plan,
            "candidates": list(plan["candidates"]),
            "review_required": True,
        }

    def motion_ai_style_apply(
        self,
        *,
        composition_id: str,
        plan: Mapping[str, Any],
        candidate_id: str,
        approved: bool,
    ) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        candidate, report = apply_style_candidate(
            composition,
            plan,
            candidate_id,
            approved=approved,
        )
        self._motion_store()[composition_id] = candidate
        self._motion_sync_owner()
        return {
            "changed": True,
            "undo_label": "Apply AI Style Direction",
            "composition_id": composition_id,
            "revision": candidate.revision,
            "report": report,
        }

    def motion_ai_style_lock_set(
        self,
        *,
        composition_id: str,
        changes: Mapping[str, Any],
    ) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        lock = set_style_lock(composition, changes)
        composition.revision += 1
        self._motion_sync_owner()
        return {
            "changed": True,
            "undo_label": "Update AI Style Lock",
            "composition_id": composition_id,
            "revision": composition.revision,
            "lock": lock,
        }

    def motion_ai_story_plan(
        self,
        *,
        composition_id: str,
        prompt: str,
    ) -> dict[str, Any]:
        return plan_story_direction(
            self._motion_store()[composition_id],
            prompt,
        )

    def motion_ai_story_apply(
        self,
        *,
        composition_id: str,
        plan: Mapping[str, Any],
        approved: bool,
    ) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        candidate, report = apply_story_direction(
            composition,
            plan,
            approved=approved,
        )
        self._motion_store()[composition_id] = candidate
        self._motion_sync_owner()
        return {
            "changed": True,
            "undo_label": "Apply AI Story Direction",
            "composition_id": composition_id,
            "revision": candidate.revision,
            "report": report,
        }

    def motion_ai_trend_preflight(
        self,
        *,
        composition_id: str,
        plan: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        return trend_preflight(
            self._motion_store()[composition_id],
            plan,
        )


__all__ = ["MotionStyleDirectorAdapterMixin"]
