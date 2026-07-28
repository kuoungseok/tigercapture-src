"""Action adapter for deterministic Motion Designer stop-motion tools."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.motion_designer.stop_motion import (
    MATERIAL_PRESETS,
    apply_stop_motion_pose,
    capture_stop_motion_pose,
    composition_stop_motion,
    effective_stop_motion,
    preflight_stop_motion,
    set_stop_motion,
    set_stop_motion_material,
    snap_stop_motion_to_audio,
    stop_motion_onion_samples,
)


class MotionStopMotionAdapterMixin:
    def _motion_stop_changed(
        self,
        composition,
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

    def motion_stop_motion_get(
        self,
        *,
        composition_id: str,
        layer_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        ids = set(layer_ids or [])
        return {
            "composition": composition_stop_motion(composition),
            "layers": {
                layer.id: effective_stop_motion(composition, layer)
                for layer in composition.layers
                if not ids or layer.id in ids
            },
            "poses": list(composition.metadata.get("stop_motion_poses") or []),
            "materials": sorted(MATERIAL_PRESETS),
        }

    def motion_stop_motion_set(
        self,
        *,
        composition_id: str,
        settings: Mapping[str, Any],
        layer_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        result = set_stop_motion(
            composition,
            settings,
            layer_ids=layer_ids or (),
        )
        return self._motion_stop_changed(
            composition,
            "Set Stop Motion Timing",
            **result,
        )

    def motion_stop_motion_pose_capture(
        self,
        *,
        composition_id: str,
        name: str,
        time_ms: int,
        layer_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        pose = capture_stop_motion_pose(
            composition,
            name=name,
            time_ms=time_ms,
            layer_ids=layer_ids or (),
        )
        return self._motion_stop_changed(
            composition,
            "Capture Stop Motion Pose",
            pose=pose,
        )

    def motion_stop_motion_pose_apply(
        self,
        *,
        composition_id: str,
        pose_id: str,
        time_ms: int | None = None,
        layer_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        result = apply_stop_motion_pose(
            composition,
            pose_id,
            time_ms=time_ms,
            layer_ids=layer_ids or (),
        )
        return self._motion_stop_changed(
            composition,
            "Apply Stop Motion Pose",
            **result,
        )

    def motion_stop_motion_material_set(
        self,
        *,
        composition_id: str,
        layer_ids: list[str],
        preset: str,
        seed: int = 17,
    ) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        result = set_stop_motion_material(
            composition,
            layer_ids,
            preset=preset,
            seed=seed,
        )
        return self._motion_stop_changed(
            composition,
            "Set Stop Motion Material",
            **result,
        )

    def motion_stop_motion_audio_snap(
        self,
        *,
        composition_id: str,
        transient_times_ms: list[int],
        layer_ids: list[str] | None = None,
        threshold_ms: int = 120,
    ) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        result = snap_stop_motion_to_audio(
            composition,
            transient_times_ms=transient_times_ms,
            layer_ids=layer_ids or (),
            threshold_ms=threshold_ms,
        )
        return self._motion_stop_changed(
            composition,
            "Snap Stop Motion To Audio",
            **result,
        )

    def motion_stop_motion_onion_inspect(
        self,
        *,
        composition_id: str,
        layer_id: str,
        time_ms: float,
        frames: int | None = None,
    ) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        return stop_motion_onion_samples(
            composition,
            layer_id=layer_id,
            time_ms=time_ms,
            frames=frames,
        )

    def motion_stop_motion_preflight(
        self,
        *,
        composition_id: str,
        layer_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        return preflight_stop_motion(
            composition,
            layer_ids=layer_ids or (),
        )


__all__ = ["MotionStopMotionAdapterMixin"]
