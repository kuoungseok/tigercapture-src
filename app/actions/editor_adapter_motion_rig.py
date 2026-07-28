"""Action adapter for Motion Designer 2D cutout rigs."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.motion_designer.rigging import (
    RIG_KIND_CUTOUT_2D,
    add_bone,
    apply_motion_preset,
    apply_pose,
    bake_two_bone_ik_constraint,
    bind_layer,
    composition_rigs,
    create_rig,
    create_humanoid_rig,
    delete_bone,
    delete_rig,
    find_rig,
    mirror_rig_bones,
    save_pose,
    remove_rig_constraint,
    set_rig_constraint_enabled,
    set_two_bone_ik_constraint,
    unbind_layer,
    update_bone,
    solve_two_bone_ik,
)


class MotionRigAdapterMixin:
    def _motion_rig_mutate(
        self,
        composition_id: str,
        operation,
        undo_label: str,
    ) -> dict[str, Any]:
        service = self._motion_service()
        result = service.mutate_rig(
            str(composition_id),
            operation,
            undo_label=undo_label,
        )
        if not result.validation.ok:
            raise ValueError(result.validation.issues[0].message)
        self._motion_commit(service)
        self._motion_sync_owner()
        return result.to_dict()

    def motion_rig_list(self, *, composition_id: str) -> dict[str, Any]:
        composition = self._motion_service().get(str(composition_id))
        rows = [rig.to_dict() for rig in composition_rigs(composition)]
        return {
            "composition_id": composition.id,
            "revision": composition.revision,
            "count": len(rows),
            "rigs": rows,
        }

    def motion_rig_inspect(
        self,
        *,
        composition_id: str,
        rig_id: str,
    ) -> dict[str, Any]:
        composition = self._motion_service().get(str(composition_id))
        rig = find_rig(composition, str(rig_id))
        return {
            "composition_id": composition.id,
            "revision": composition.revision,
            "rig": rig.to_dict(),
        }

    def motion_rig_create(
        self,
        *,
        composition_id: str,
        name: str = "2D Character Rig",
        kind: str = RIG_KIND_CUTOUT_2D,
        bones: Sequence[Mapping[str, Any]] = (),
        bindings: Sequence[Mapping[str, Any]] = (),
    ) -> dict[str, Any]:
        return self._motion_rig_mutate(
            composition_id,
            lambda composition: {
                "rig": create_rig(
                    composition,
                    name=str(name),
                    kind=str(kind),
                    bones=bones,
                    bindings=bindings,
                ).to_dict(),
            },
            "Create Motion Rig",
        )

    def motion_rig_delete(
        self,
        *,
        composition_id: str,
        rig_id: str,
    ) -> dict[str, Any]:
        def operation(composition):
            if not delete_rig(composition, rig_id):
                raise ValueError(f"Unknown motion rig: {rig_id}")
            return {"rig_id": str(rig_id)}

        return self._motion_rig_mutate(
            composition_id, operation, "Delete Motion Rig",
        )

    def motion_rig_humanoid_create(
        self,
        *,
        composition_id: str,
        name: str = "Humanoid Cutout Rig",
        layer_slots: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        return self._motion_rig_mutate(
            composition_id,
            lambda composition: {
                "rig": create_humanoid_rig(
                    composition,
                    name=name,
                    layer_slots=layer_slots,
                ).to_dict(),
            },
            "Create Humanoid Motion Rig",
        )

    def motion_rig_bone_add(
        self,
        *,
        composition_id: str,
        rig_id: str,
        bone: Mapping[str, Any],
    ) -> dict[str, Any]:
        return self._motion_rig_mutate(
            composition_id,
            lambda composition: {
                "rig_id": str(rig_id),
                "bone": add_bone(composition, rig_id, bone).to_dict(),
            },
            "Add Rig Bone",
        )

    def motion_rig_bone_update(
        self,
        *,
        composition_id: str,
        rig_id: str,
        bone_id: str,
        changes: Mapping[str, Any],
    ) -> dict[str, Any]:
        return self._motion_rig_mutate(
            composition_id,
            lambda composition: {
                "rig_id": str(rig_id),
                "bone": update_bone(
                    composition, rig_id, bone_id, changes,
                ).to_dict(),
            },
            "Update Rig Bone",
        )

    def motion_rig_bone_delete(
        self,
        *,
        composition_id: str,
        rig_id: str,
        bone_id: str,
    ) -> dict[str, Any]:
        def operation(composition):
            if not delete_bone(composition, rig_id, bone_id):
                raise ValueError(f"Unknown rig bone: {bone_id}")
            return {"rig_id": str(rig_id), "bone_id": str(bone_id)}

        return self._motion_rig_mutate(
            composition_id, operation, "Delete Rig Bone",
        )

    def motion_rig_bone_mirror(
        self,
        *,
        composition_id: str,
        rig_id: str,
        bone_ids: Sequence[str] = (),
        axis_x: float | None = None,
        create_missing: bool = True,
    ) -> dict[str, Any]:
        return self._motion_rig_mutate(
            composition_id,
            lambda composition: {
                "mirror": mirror_rig_bones(
                    composition,
                    rig_id,
                    bone_ids=bone_ids,
                    axis_x=axis_x,
                    create_missing=create_missing,
                ),
            },
            "Mirror Rig Bones",
        )

    def motion_rig_layer_bind(
        self,
        *,
        composition_id: str,
        rig_id: str,
        bone_id: str,
        layer_id: str,
        inherit_rotation: bool = True,
        inherit_scale: bool = True,
    ) -> dict[str, Any]:
        return self._motion_rig_mutate(
            composition_id,
            lambda composition: {
                "rig_id": str(rig_id),
                "binding": bind_layer(
                    composition,
                    rig_id,
                    layer_id,
                    bone_id,
                    inherit_rotation=inherit_rotation,
                    inherit_scale=inherit_scale,
                ).to_dict(),
            },
            "Bind Layer to Rig",
        )

    def motion_rig_layer_unbind(
        self,
        *,
        composition_id: str,
        rig_id: str,
        layer_id: str,
    ) -> dict[str, Any]:
        def operation(composition):
            if not unbind_layer(composition, rig_id, layer_id):
                raise ValueError(f"Rig layer binding not found: {layer_id}")
            return {"rig_id": str(rig_id), "layer_id": str(layer_id)}

        return self._motion_rig_mutate(
            composition_id, operation, "Unbind Layer from Rig",
        )

    def motion_rig_ik_solve(
        self,
        *,
        composition_id: str,
        rig_id: str,
        root_bone_id: str,
        mid_bone_id: str,
        end_bone_id: str,
        target: Sequence[float],
        pole: Sequence[float] | None = None,
        time_ms: int | None = None,
    ) -> dict[str, Any]:
        return self._motion_rig_mutate(
            composition_id,
            lambda composition: {
                "ik": solve_two_bone_ik(
                    composition,
                    rig_id,
                    root_bone_id=root_bone_id,
                    mid_bone_id=mid_bone_id,
                    end_bone_id=end_bone_id,
                    target=target,
                    pole=pole,
                    time_ms=time_ms,
                ),
            },
            "Solve Rig IK",
        )

    def motion_rig_constraint_set(
        self,
        *,
        composition_id: str,
        rig_id: str,
        root_bone_id: str,
        mid_bone_id: str,
        end_bone_id: str,
        target: Sequence[float] | Mapping[str, Any],
        pole: Sequence[float] | Mapping[str, Any] | None = None,
        weight: float | Mapping[str, Any] = 1.0,
        constraint_id: str = "",
        enabled: bool = True,
        lock_end: bool = True,
    ) -> dict[str, Any]:
        return self._motion_rig_mutate(
            composition_id,
            lambda composition: {
                "constraint": set_two_bone_ik_constraint(
                    composition,
                    rig_id,
                    root_bone_id=root_bone_id,
                    mid_bone_id=mid_bone_id,
                    end_bone_id=end_bone_id,
                    target=target,
                    pole=pole,
                    weight=weight,
                    constraint_id=constraint_id,
                    enabled=enabled,
                    lock_end=lock_end,
                ),
            },
            "Set Rig IK Constraint",
        )

    def motion_rig_constraint_remove(
        self,
        *,
        composition_id: str,
        rig_id: str,
        constraint_id: str,
    ) -> dict[str, Any]:
        def operation(composition):
            if not remove_rig_constraint(composition, rig_id, constraint_id):
                raise ValueError(f"Unknown rig constraint: {constraint_id}")
            return {"rig_id": str(rig_id), "constraint_id": str(constraint_id)}

        return self._motion_rig_mutate(
            composition_id, operation, "Remove Rig IK Constraint",
        )

    def motion_rig_constraint_enable(
        self,
        *,
        composition_id: str,
        rig_id: str,
        constraint_id: str,
        enabled: bool,
    ) -> dict[str, Any]:
        return self._motion_rig_mutate(
            composition_id,
            lambda composition: {
                "constraint": set_rig_constraint_enabled(
                    composition, rig_id, constraint_id, enabled,
                ),
            },
            "Switch Rig FK IK",
        )

    def motion_rig_ik_bake(
        self,
        *,
        composition_id: str,
        rig_id: str,
        constraint_id: str,
        start_ms: int = 0,
        end_ms: int | None = None,
        sample_fps: float | None = None,
        disable_after: bool = True,
    ) -> dict[str, Any]:
        return self._motion_rig_mutate(
            composition_id,
            lambda composition: {
                "bake": bake_two_bone_ik_constraint(
                    composition,
                    rig_id,
                    constraint_id,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    sample_fps=sample_fps,
                    disable_after=disable_after,
                ),
            },
            "Bake Rig IK to FK",
        )

    def motion_rig_pose_save(
        self,
        *,
        composition_id: str,
        rig_id: str,
        name: str,
        time_ms: int = 0,
    ) -> dict[str, Any]:
        return self._motion_rig_mutate(
            composition_id,
            lambda composition: {
                "rig_id": str(rig_id),
                "pose": save_pose(
                    composition, rig_id, name=name, time_ms=time_ms,
                ),
            },
            "Save Rig Pose",
        )

    def motion_rig_pose_apply(
        self,
        *,
        composition_id: str,
        rig_id: str,
        pose_id: str,
        time_ms: int | None = None,
        mirrored: bool = False,
    ) -> dict[str, Any]:
        return self._motion_rig_mutate(
            composition_id,
            lambda composition: {
                "pose": apply_pose(
                    composition,
                    rig_id,
                    pose_id,
                    time_ms=time_ms,
                    mirrored=mirrored,
                ),
            },
            "Apply Rig Pose",
        )

    def motion_rig_motion_apply(
        self,
        *,
        composition_id: str,
        rig_id: str,
        preset_id: str,
        start_ms: int = 0,
        end_ms: int | None = None,
        side: str = "right",
    ) -> dict[str, Any]:
        return self._motion_rig_mutate(
            composition_id,
            lambda composition: {
                "motion": apply_motion_preset(
                    composition,
                    rig_id,
                    preset_id,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    side=side,
                ),
            },
            "Apply Rig Motion",
        )


__all__ = ["MotionRigAdapterMixin"]
