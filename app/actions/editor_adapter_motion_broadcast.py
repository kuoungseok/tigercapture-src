"""Motion Designer broadcast bridge actions."""
from __future__ import annotations

from typing import Any, Mapping

from app.motion_designer.broadcast_bridge import (
    apply_live_controls,
    broadcast_preflight,
    render_stinger_alpha_cache,
    stinger_alpha_plan,
)


class MotionBroadcastAdapterMixin:
    def motion_broadcast_preflight(self, *, composition_id: str,
                                   cache_manifest: Mapping[str, Any] | None = None) -> dict[str, Any]:
        composition = self._motion_store().get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        return broadcast_preflight(composition, cache_manifest=cache_manifest)

    def motion_broadcast_live_control_set(self, *, composition_id: str,
                                          changes: Mapping[str, Any]) -> dict[str, Any]:
        store = self._motion_store()
        composition = store.get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        candidate = apply_live_controls(composition, changes)
        store[composition_id] = candidate
        self._motion_sync_owner()
        return {
            "changed": candidate.to_dict() != composition.to_dict(),
            "undo_label": "Set Motion Broadcast Live Controls",
            "composition_id": candidate.id,
            "composition_revision": candidate.revision,
            "published_controls": candidate.metadata["last_applied_template"]["published_controls"],
            "cache_invalidated": "broadcast_cache" not in candidate.metadata,
        }

    def motion_broadcast_stinger_plan(self, *, composition_id: str, output_dir: str,
                                      fps: float | None = None) -> dict[str, Any]:
        composition = self._motion_store().get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        return stinger_alpha_plan(composition, output_dir, fps=fps)

    def motion_broadcast_stinger_render(self, *, composition_id: str, output_dir: str,
                                        fps: float | None = None) -> dict[str, Any]:
        store = self._motion_store()
        composition = store.get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        candidate, manifest = render_stinger_alpha_cache(composition, output_dir, fps=fps)
        store[composition_id] = candidate
        self._motion_sync_owner()
        return {
            "changed": True,
            "undo_label": "Render Motion Broadcast Alpha Cache",
            "composition_id": composition_id,
            "composition_revision": candidate.revision,
            "cache": manifest,
            "preflight": broadcast_preflight(candidate),
        }


__all__ = ["MotionBroadcastAdapterMixin"]
