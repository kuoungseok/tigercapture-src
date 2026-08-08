"""Motion project asset relink actions."""
from __future__ import annotations

from typing import Any

from app.motion_designer.relink import apply_motion_relink, build_motion_relink_plan


class MotionRelinkAdapterMixin:
    def motion_source_relink_plan(self, *, composition_id: str, old_root: str,
                                  new_root: str) -> dict[str, Any]:
        composition = self._motion_store().get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        return build_motion_relink_plan(composition, old_root=old_root, new_root=new_root)

    def motion_source_relink_apply(self, *, composition_id: str, old_root: str,
                                   new_root: str, allow_partial: bool = False) -> dict[str, Any]:
        store = self._motion_store()
        composition = store.get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        candidate, result = apply_motion_relink(
            composition, old_root=old_root, new_root=new_root, allow_partial=allow_partial,
        )
        store[composition_id] = candidate
        self._motion_sync_owner()
        return {**result, "undo_label": "Relink Motion Sources", "composition": candidate.to_dict()}


__all__ = ["MotionRelinkAdapterMixin"]
