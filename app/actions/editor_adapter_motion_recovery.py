"""Motion autosave and recovery actions."""
from __future__ import annotations

from typing import Any

from app.motion_designer.recovery import (
    default_motion_recovery_root, list_motion_recoveries, motion_recovery_path,
    read_motion_recovery, write_motion_recovery,
)


class MotionRecoveryAdapterMixin:
    def motion_recovery_write(self, *, composition_id: str, recovery_root: str = "",
                              project_path: str = "") -> dict[str, Any]:
        composition = self._motion_store().get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        root = recovery_root or str(default_motion_recovery_root(project_path or None))
        return write_motion_recovery(
            composition, motion_recovery_path(root, composition.id), project_path=project_path or None,
        )

    def motion_recovery_list(self, *, recovery_root: str = "", project_path: str = "") -> dict[str, Any]:
        root = recovery_root or str(default_motion_recovery_root(project_path or None))
        return list_motion_recoveries(root)

    def motion_recovery_apply(self, *, composition_id: str, path: str,
                              allow_stale: bool = False) -> dict[str, Any]:
        store = self._motion_store()
        current = store.get(composition_id)
        if current is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        recovered, report = read_motion_recovery(
            path, expected_composition_id=composition_id, current_revision=current.revision,
            allow_stale=allow_stale,
        )
        store[composition_id] = recovered
        self._motion_sync_owner()
        return {**report, "changed": recovered.to_dict() != current.to_dict(),
                "undo_label": "Recover Motion Composition", "composition": recovered.to_dict()}


__all__ = ["MotionRecoveryAdapterMixin"]
