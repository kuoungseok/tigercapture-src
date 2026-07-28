from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QElapsedTimer, QThread, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QDockWidget, QFileDialog, QListWidget, QMainWindow, QMessageBox,
    QSplitter, QTabWidget, QVBoxLayout, QWidget,
)

from app.motion_designer.ai_workspace import apply_motion_ai_proposal
from app.motion_designer.commands import find_layer, set_keyframe
from app.motion_designer.composition_service import CompositionService
from app.motion_designer.evaluator import remap_layer_time
from app.motion_designer.schema import (
    AnimatedProperty, Keyframe, MotionBehaviorRef, MotionComposition,
    MotionEffectRef, MotionLayer, MotionMaskRef, SourceRef,
)
from app.motion_designer.vector_shapes import default_pen_path
from app.motion_designer.localization import motion_text, retranslate_motion_ui
from app.i18n import current_language, save_language, set_language

from .behavior_panel import BehaviorPanel
from .button_panel import ButtonComponentPanel
from .audio_panel import AudioReactivePanel
from .audio_worker import MotionAudioAnalysisWorker
from .ai_panel import MotionAIPanel
from .ai_worker import (
    MotionAICandidatePreviewWorker,
    MotionAIGenerationWorker,
    MotionAIPatchWorker,
)
from .ar_pbr_panel import ArPbrPanel
from .actor_panel import ActorPanel
from .advanced_panel import AdvancedMotionPanel
from .canvas import MotionCanvas
from .cutout_rig_dialog import CutoutArmRigDialog
from .full_body_rig_dialog import FullBodyRigDialog
from .effect_mask_panel import EffectMaskPanel
from .export_panel import MotionOutputPanel
from .export_worker import MotionExportWorker
from .generator_panel import GeneratorPanel
from .inspector import InspectorPanel
from .craft_panel import CraftStylePanel
from .image_panel import ImagePanel
from .layer_panel import LayerPanel
from .library_panel import MotionLibraryPanel
from .mmd_panel import MMDPanel
from .particle_panel import ParticlePanel
from .puppet_panel import PuppetPanel
from .replicator_panel import ReplicatorPanel
from .rig_panel import RigPanel
from .vrm_panel import VRMPanel
from .style import MOTION_DESIGNER_QSS
from .timeline import MotionTimeline
from .toolbar import MotionToolbar
from .template_gallery import MotionTemplateGalleryDialog
from .tracking_worker import MotionFaceTrackingWorker, MotionTrackingWorker
from .tracking_panel import TrackingPanel
from .typography_panel import TypographyPanel
from .umg_panel import MotionUnrealLinkDialog
from .umg_worker import MotionUMGGenerationWorker
from .viewer_header import ViewerHeader
from .vector_panel import VectorPanel
from app.motion_designer.preview_renderer import MotionPreviewWidget


class MotionDocumentController:
    """Single mutation entry point for the desktop UI."""

    def __init__(self, composition: MotionComposition, changed: Callable[[MotionComposition], None]) -> None:
        self.composition = MotionComposition.from_dict(composition.to_dict())
        self._changed = changed
        self._snapshots = [self.composition.to_dict()]
        self._history_index = 0

    def _commit(self, composition: MotionComposition) -> None:
        self.composition = composition
        self._snapshots = self._snapshots[: self._history_index + 1]
        self._snapshots.append(deepcopy(composition.to_dict()))
        self._history_index += 1
        self._changed(self.composition)

    def add_layer(self, layer: MotionLayer) -> None:
        service = CompositionService([self.composition])
        result = service.add_layer(self.composition.id, layer)
        if not result.validation.ok:
            raise ValueError(result.validation.issues[0].message)
        self._commit(service.get(self.composition.id))

    def update_layer(self, layer_id: str, changes: dict) -> None:
        service = CompositionService([self.composition])
        result = service.update_layer(self.composition.id, layer_id, changes)
        if not result.validation.ok:
            raise ValueError(result.validation.issues[0].message)
        self._commit(service.get(self.composition.id))

    def set_adjustment_scope(
        self,
        layer_id: str,
        mode: str,
        layer_ids: list[str],
    ) -> None:
        from app.motion_designer.adjustment_scope import set_adjustment_scope

        candidate = MotionComposition.from_dict(self.composition.to_dict())
        layer = find_layer(candidate, layer_id)
        set_adjustment_scope(
            candidate,
            layer,
            mode=mode,
            layer_ids=layer_ids,
        )
        candidate.revision += 1
        self._commit(candidate)

    def set_effect_group_scope(
        self,
        layer_id: str,
        mode: str,
        layer_ids: list[str],
    ) -> None:
        from app.motion_designer.effect_group import set_effect_group_scope

        candidate = MotionComposition.from_dict(self.composition.to_dict())
        layer = find_layer(candidate, layer_id)
        set_effect_group_scope(
            candidate,
            layer,
            enabled=True,
            mode=mode,
            layer_ids=layer_ids,
        )
        candidate.revision += 1
        self._commit(candidate)

    def update_composition_metadata(self, changes: dict) -> None:
        candidate = MotionComposition.from_dict(self.composition.to_dict())
        candidate.metadata.update(deepcopy(changes))
        candidate.revision += 1
        self._commit(candidate)

    def update_rig_bone(
        self,
        rig_id: str,
        bone_id: str,
        changes: dict,
    ) -> None:
        from app.motion_designer.rigging import update_bone

        service = CompositionService([self.composition])
        result = service.mutate_rig(
            self.composition.id,
            lambda candidate: {
                "rig_id": str(rig_id),
                "bone": update_bone(
                    candidate, str(rig_id), str(bone_id), changes,
                ).to_dict(),
            },
            undo_label="Update Rig Bone",
        )
        if not result.validation.ok:
            raise ValueError(result.validation.issues[0].message)
        self._commit(service.get(self.composition.id))

    def mirror_rig_bone(self, rig_id: str, bone_id: str) -> None:
        from app.motion_designer.rigging import mirror_rig_bones

        service = CompositionService([self.composition])
        result = service.mutate_rig(
            self.composition.id,
            lambda candidate: {
                "mirror": mirror_rig_bones(
                    candidate,
                    str(rig_id),
                    bone_ids=[str(bone_id)],
                    create_missing=True,
                ),
            },
            undo_label="Mirror Rig Bone",
        )
        if not result.validation.ok:
            raise ValueError(result.validation.issues[0].message)
        self._commit(service.get(self.composition.id))

    def create_rig_ik_lock(self, rig_id: str, end_bone_id: str) -> None:
        from app.motion_designer.rigging import (
            find_rig,
            set_two_bone_ik_constraint,
        )

        service = CompositionService([self.composition])

        def operation(candidate):
            rig = find_rig(candidate, rig_id)
            by_id = {bone.id: bone for bone in rig.bones}
            end = by_id.get(end_bone_id)
            mid = by_id.get(end.parent_id) if end is not None else None
            root = by_id.get(mid.parent_id) if mid is not None else None
            if end is None or mid is None or root is None:
                raise ValueError(
                    "IK Lock requires a selected end bone with two parents",
                )
            dx = end.rest_position[0] - root.rest_position[0]
            dy = end.rest_position[1] - root.rest_position[1]
            pole = [
                mid.rest_position[0] - dy * 0.35,
                mid.rest_position[1] + dx * 0.35,
            ]
            return {
                "constraint": set_two_bone_ik_constraint(
                    candidate,
                    rig_id,
                    root_bone_id=root.id,
                    mid_bone_id=mid.id,
                    end_bone_id=end.id,
                    target=list(end.rest_position),
                    pole=pole,
                    lock_end=True,
                ),
            }

        result = service.mutate_rig(
            self.composition.id,
            operation,
            undo_label="Create Rig IK Lock",
        )
        if not result.validation.ok:
            raise ValueError(result.validation.issues[0].message)
        self._commit(service.get(self.composition.id))

    def set_rig_constraint_enabled(
        self,
        rig_id: str,
        constraint_id: str,
        enabled: bool,
    ) -> None:
        from app.motion_designer.rigging import set_rig_constraint_enabled

        service = CompositionService([self.composition])
        result = service.mutate_rig(
            self.composition.id,
            lambda candidate: {
                "constraint": set_rig_constraint_enabled(
                    candidate, rig_id, constraint_id, enabled,
                ),
            },
            undo_label="Switch Rig FK IK",
        )
        if not result.validation.ok:
            raise ValueError(result.validation.issues[0].message)
        self._commit(service.get(self.composition.id))

    def bake_rig_constraint(self, rig_id: str, constraint_id: str) -> None:
        from app.motion_designer.rigging import bake_two_bone_ik_constraint

        service = CompositionService([self.composition])
        result = service.mutate_rig(
            self.composition.id,
            lambda candidate: {
                "bake": bake_two_bone_ik_constraint(
                    candidate,
                    rig_id,
                    constraint_id,
                    start_ms=0,
                    end_ms=candidate.duration_ms,
                    sample_fps=candidate.fps,
                    disable_after=True,
                ),
            },
            undo_label="Bake Rig IK to FK",
        )
        if not result.validation.ok:
            raise ValueError(result.validation.issues[0].message)
        self._commit(service.get(self.composition.id))

    def move_puppet_pin(
        self,
        layer_id: str,
        pin_id: str,
        x: float,
        y: float,
    ) -> None:
        from app.motion_designer.puppet_mesh import update_puppet_pin

        candidate = MotionComposition.from_dict(self.composition.to_dict())
        layer = find_layer(candidate, layer_id)
        pin = update_puppet_pin(
            layer,
            pin_id,
            {
                "rest_position": [float(x), float(y)],
                "position": [float(x), float(y)],
            },
        )
        if not pin.id:
            raise ValueError(f"Unknown puppet pin: {pin_id}")
        candidate.revision += 1
        service = CompositionService([candidate])
        self._commit(service.get(candidate.id))

    def create_puppet_mesh(
        self,
        layer_id: str,
        columns: int,
        rows: int,
        adaptive: bool = True,
    ) -> None:
        from app.motion_designer.puppet_mesh import (
            create_alpha_adaptive_puppet_mesh,
            create_grid_puppet_mesh,
        )

        candidate = MotionComposition.from_dict(self.composition.to_dict())
        layer = find_layer(candidate, layer_id)
        creator = (
            create_alpha_adaptive_puppet_mesh
            if adaptive
            else create_grid_puppet_mesh
        )
        creator(layer, columns=columns, rows=rows)
        candidate.revision += 1
        service = CompositionService([candidate])
        self._commit(service.get(candidate.id))

    def configure_puppet_tear_repair(
        self,
        layer_id: str,
        settings: dict,
    ) -> None:
        from app.motion_designer.puppet_mesh import configure_puppet_tear_repair

        candidate = MotionComposition.from_dict(self.composition.to_dict())
        layer = find_layer(candidate, layer_id)
        configure_puppet_tear_repair(
            layer,
            enabled=bool(settings.get("enabled", True)),
            max_edge_stretch=float(
                settings.get("max_edge_stretch", 6.0) or 6.0
            ),
        )
        candidate.revision += 1
        self._commit(candidate)

    def add_puppet_pin(self, layer_id: str, kind: str) -> None:
        from app.motion_designer.puppet_mesh import add_puppet_pin

        candidate = MotionComposition.from_dict(self.composition.to_dict())
        layer = find_layer(candidate, layer_id)
        add_puppet_pin(
            layer,
            kind=kind,
            position=[0.5, 0.5],
            name=str(kind).title(),
        )
        candidate.revision += 1
        service = CompositionService([candidate])
        self._commit(service.get(candidate.id))

    def update_puppet_pin(
        self,
        layer_id: str,
        pin_id: str,
        changes: dict,
    ) -> None:
        from app.motion_designer.puppet_mesh import update_puppet_pin

        candidate = MotionComposition.from_dict(self.composition.to_dict())
        layer = find_layer(candidate, layer_id)
        update_puppet_pin(layer, pin_id, changes)
        candidate.revision += 1
        service = CompositionService([candidate])
        self._commit(service.get(candidate.id))

    def update_puppet_keyframe(
        self,
        layer_id: str,
        pin_id: str,
        property_name: str,
        keyframe_id: str,
        time_ms: int,
        value,
    ) -> None:
        from app.motion_designer.puppet_mesh import (
            layer_puppet_mesh,
            set_layer_puppet_mesh,
        )

        candidate = MotionComposition.from_dict(self.composition.to_dict())
        layer = find_layer(candidate, layer_id)
        mesh = layer_puppet_mesh(layer)
        if mesh is None:
            raise ValueError("Layer has no puppet mesh")
        pin = next((row for row in mesh.pins if row.id == pin_id), None)
        if pin is None:
            raise ValueError(f"Unknown puppet pin: {pin_id}")
        prop = {
            "position": pin.position,
            "rotation": pin.rotation,
        }.get(str(property_name))
        if prop is None:
            raise ValueError(f"Unknown puppet pin property: {property_name}")
        keyframe = next(
            (row for row in prop.keyframes if row.id == keyframe_id),
            None,
        )
        if keyframe is None:
            raise ValueError(f"Unknown puppet keyframe: {keyframe_id}")
        target_time = max(0, min(candidate.duration_ms, int(time_ms)))
        prop.keyframes = [
            row
            for row in prop.keyframes
            if row.id == keyframe_id or row.time_ms != target_time
        ]
        keyframe.time_ms = target_time
        keyframe.value = value
        prop.keyframes.sort(key=lambda row: (row.time_ms, row.id))
        set_layer_puppet_mesh(layer, mesh)
        candidate.revision += 1
        service = CompositionService([candidate])
        self._commit(service.get(candidate.id))

    def delete_layer(self, layer_id: str) -> None:
        service = CompositionService([self.composition])
        result = service.delete_layer(self.composition.id, layer_id)
        if not result.validation.ok:
            raise ValueError(result.validation.issues[0].message)
        self._commit(service.get(self.composition.id))

    def duplicate_layer(self, layer_id: str) -> str:
        service = CompositionService([self.composition])
        result = service.duplicate_layer(self.composition.id, layer_id)
        if not result.validation.ok:
            raise ValueError(result.validation.issues[0].message)
        source_ids = {item.id for item in self.composition.layers}
        candidate = service.get(self.composition.id)
        duplicate_id = next(item.id for item in candidate.layers if item.id not in source_ids)
        self._commit(candidate)
        return duplicate_id

    def apply_layer_structure(self, rows: list[dict[str, str]]) -> None:
        candidate = MotionComposition.from_dict(self.composition.to_dict())
        by_id = {item.id: item for item in candidate.layers}
        ordered_ids = [str(row.get("id") or "") for row in rows if str(row.get("id") or "") in by_id]
        if len(set(ordered_ids)) != len(candidate.layers):
            raise ValueError("Layer structure must contain every layer exactly once")
        for row in rows:
            layer = by_id.get(str(row.get("id") or ""))
            if layer is not None:
                layer.parent_id = str(row.get("parent_id") or "")
        candidate.layers = [by_id[layer_id] for layer_id in reversed(ordered_ids)]
        candidate.revision += 1
        CompositionService([candidate])
        self._commit(candidate)

    def set_keyframe(self, layer_id: str, property_name: str, value, time_ms: int) -> None:
        candidate = MotionComposition.from_dict(self.composition.to_dict())
        set_keyframe(candidate, layer_id, property_name, Keyframe(time_ms=time_ms, value=value))
        self._commit(candidate)

    def set_source_keyframe(
        self,
        layer_id: str,
        parameter_name: str,
        value,
        time_ms: int,
    ) -> None:
        candidate = MotionComposition.from_dict(self.composition.to_dict())
        layer = find_layer(candidate, layer_id)
        current = layer.source.params.get(parameter_name, value)
        prop = (
            AnimatedProperty.from_dict(current)
            if isinstance(current, dict)
            and ("default" in current or "keyframes" in current)
            else AnimatedProperty(value_type="scalar", default=float(current))
        )
        frame = Keyframe(time_ms=max(0, int(time_ms)), value=float(value))
        prop.keyframes = [
            item
            for item in prop.keyframes
            if item.id != frame.id and item.time_ms != frame.time_ms
        ]
        prop.keyframes.append(frame)
        prop.keyframes.sort(key=lambda item: (item.time_ms, item.id))
        layer.source.params[parameter_name] = prop.to_dict()
        candidate.revision += 1
        self._commit(candidate)

    def set_effect_parameter(
        self,
        layer_id: str,
        effect_id: str,
        parameter_name: str,
        value,
        time_ms: int | None = None,
    ) -> None:
        self._set_effect_mask_parameter(
            layer_id,
            "effects",
            effect_id,
            parameter_name,
            value,
            time_ms=time_ms,
        )

    def set_mask_parameter(
        self,
        layer_id: str,
        mask_id: str,
        parameter_name: str,
        value,
        time_ms: int | None = None,
    ) -> None:
        self._set_effect_mask_parameter(
            layer_id,
            "masks",
            mask_id,
            parameter_name,
            value,
            time_ms=time_ms,
        )

    def remove_effect_keyframe(
        self,
        layer_id: str,
        effect_id: str,
        parameter_name: str,
        time_ms: int,
    ) -> None:
        self._remove_effect_mask_keyframe(
            layer_id, "effects", effect_id, parameter_name, time_ms,
        )

    def remove_mask_keyframe(
        self,
        layer_id: str,
        mask_id: str,
        parameter_name: str,
        time_ms: int,
    ) -> None:
        self._remove_effect_mask_keyframe(
            layer_id, "masks", mask_id, parameter_name, time_ms,
        )

    def _set_effect_mask_parameter(
        self,
        layer_id: str,
        collection_name: str,
        item_id: str,
        parameter_name: str,
        value,
        *,
        time_ms: int | None,
    ) -> None:
        candidate = MotionComposition.from_dict(self.composition.to_dict())
        layer = find_layer(candidate, layer_id)
        collection = getattr(layer, collection_name)
        item = next((row for row in collection if row.id == item_id), None)
        if item is None:
            raise ValueError(f"Unknown Motion {collection_name[:-1]}: {item_id}")
        prop = item.params.setdefault(
            str(parameter_name),
            AnimatedProperty(default=value),
        )
        if time_ms is None:
            prop.default = value
        else:
            target_time = max(0, int(round(time_ms)))
            existing = next(
                (row for row in prop.keyframes if int(row.time_ms) == target_time),
                None,
            )
            if existing is None:
                prop.keyframes.append(Keyframe(time_ms=target_time, value=value))
            else:
                existing.value = value
            prop.keyframes.sort(key=lambda row: (row.time_ms, row.id))
        candidate.revision += 1
        self._commit(candidate)

    def _remove_effect_mask_keyframe(
        self,
        layer_id: str,
        collection_name: str,
        item_id: str,
        parameter_name: str,
        time_ms: int,
    ) -> None:
        candidate = MotionComposition.from_dict(self.composition.to_dict())
        layer = find_layer(candidate, layer_id)
        collection = getattr(layer, collection_name)
        item = next((row for row in collection if row.id == item_id), None)
        if item is None:
            raise ValueError(f"Unknown Motion {collection_name[:-1]}: {item_id}")
        prop = item.params.get(str(parameter_name))
        if prop is None:
            return
        target_time = max(0, int(round(time_ms)))
        remaining = [
            row for row in prop.keyframes
            if int(row.time_ms) != target_time
        ]
        if len(remaining) == len(prop.keyframes):
            return
        prop.keyframes = remaining
        candidate.revision += 1
        self._commit(candidate)

    def update_keyframe(
        self, layer_id: str, property_name: str, keyframe_id: str, time_ms: int, value,
    ) -> None:
        candidate = MotionComposition.from_dict(self.composition.to_dict())
        layer = find_layer(candidate, layer_id)
        if str(property_name).startswith("source:"):
            parameter_name = str(property_name).split(":", 1)[1]
            current = layer.source.params.get(parameter_name)
            prop = (
                AnimatedProperty.from_dict(current)
                if isinstance(current, dict)
                and ("default" in current or "keyframes" in current)
                else None
            )
        elif str(property_name) == "time_remap":
            from app.motion_designer.time_remap import layer_time_remap

            parameter_name = "time_remap"
            prop = layer_time_remap(layer)
        else:
            parameter_name = ""
            prop = layer.transform.properties().get(property_name)
        if prop is None:
            raise ValueError(f"Unknown animated property: {property_name}")
        keyframe = next((item for item in prop.keyframes if item.id == keyframe_id), None)
        if keyframe is None:
            raise ValueError(f"Unknown keyframe: {keyframe_id}")
        target_time_ms = max(0, min(candidate.duration_ms, int(time_ms)))
        prop.keyframes = [
            item for item in prop.keyframes
            if item.id == keyframe_id or item.time_ms != target_time_ms
        ]
        keyframe.time_ms = target_time_ms
        keyframe.value = value
        prop.keyframes.sort(key=lambda item: (item.time_ms, item.id))
        if parameter_name == "time_remap":
            from app.motion_designer.time_remap import TIME_REMAP_CONTRACT

            layer.metadata["time_remap"] = {
                "contract": TIME_REMAP_CONTRACT,
                "enabled": True,
                "property": prop.to_dict(),
            }
        elif parameter_name:
            layer.source.params[parameter_name] = prop.to_dict()
        candidate.revision += 1
        self._commit(candidate)

    def update_keyframe_tangent(
        self,
        layer_id: str,
        property_name: str,
        keyframe_id: str,
        mode: str,
    ) -> None:
        from app.motion_designer.graph_editing import update_keyframe_tangent

        candidate = MotionComposition.from_dict(self.composition.to_dict())
        layer = find_layer(candidate, layer_id)
        update_keyframe_tangent(
            layer,
            property_name,
            keyframe_id,
            mode=mode,
        )
        candidate.revision += 1
        self._commit(candidate)

    def set_keyframe_roving(
        self,
        layer_id: str,
        property_name: str,
        keyframe_id: str,
    ) -> None:
        from app.motion_designer.graph_editing import set_roving_keyframes

        candidate = MotionComposition.from_dict(self.composition.to_dict())
        layer = find_layer(candidate, layer_id)
        set_roving_keyframes(
            layer,
            property_name,
            [keyframe_id],
            enabled=True,
        )
        candidate.revision += 1
        self._commit(candidate)

    def update_keyframe_tangent_value(
        self,
        layer_id: str,
        property_name: str,
        keyframe_id: str,
        side: str,
        value,
    ) -> None:
        from app.motion_designer.graph_editing import update_keyframe_tangent

        candidate = MotionComposition.from_dict(self.composition.to_dict())
        layer = find_layer(candidate, layer_id)
        update_keyframe_tangent(
            layer,
            property_name,
            keyframe_id,
            mode="broken",
            in_tangent=value if str(side) == "in" else None,
            out_tangent=value if str(side) == "out" else None,
        )
        candidate.revision += 1
        self._commit(candidate)

    def update_rig_keyframe(
        self,
        rig_id: str,
        bone_id: str,
        property_name: str,
        keyframe_id: str,
        time_ms: int,
        value,
    ) -> None:
        from app.motion_designer.rigging import find_rig, upsert_rig

        candidate = MotionComposition.from_dict(self.composition.to_dict())
        rig = find_rig(candidate, rig_id)
        bone = next((row for row in rig.bones if row.id == bone_id), None)
        if bone is None:
            raise ValueError(f"Unknown rig bone: {bone_id}")
        prop = {
            "rotation": bone.rotation,
            "translation": bone.translation,
        }.get(str(property_name))
        if prop is None:
            raise ValueError(f"Unknown rig animated property: {property_name}")
        keyframe = next(
            (item for item in prop.keyframes if item.id == keyframe_id),
            None,
        )
        if keyframe is None:
            raise ValueError(f"Unknown rig keyframe: {keyframe_id}")
        target_time_ms = max(0, min(candidate.duration_ms, int(time_ms)))
        prop.keyframes = [
            item
            for item in prop.keyframes
            if item.id == keyframe_id or item.time_ms != target_time_ms
        ]
        keyframe.time_ms = target_time_ms
        keyframe.value = value
        prop.keyframes.sort(key=lambda item: (item.time_ms, item.id))
        upsert_rig(candidate, rig)
        candidate.revision += 1
        self._commit(candidate)

    def undo(self) -> None:
        if self._history_index <= 0:
            return
        self._history_index -= 1
        self.composition = MotionComposition.from_dict(self._snapshots[self._history_index])
        self._changed(self.composition)

    def redo(self) -> None:
        if self._history_index >= len(self._snapshots) - 1:
            return
        self._history_index += 1
        self.composition = MotionComposition.from_dict(self._snapshots[self._history_index])
        self._changed(self.composition)

    def replace(self, composition: MotionComposition) -> None:
        candidate = MotionComposition.from_dict(composition.to_dict())
        CompositionService([candidate])
        self._commit(candidate)

    def load(self, composition: MotionComposition) -> None:
        candidate = MotionComposition.from_dict(composition.to_dict())
        CompositionService([candidate])
        self.composition = candidate
        self._snapshots = [candidate.to_dict()]
        self._history_index = 0
        self._changed(candidate)


class MotionDesignerWindow(QMainWindow):
    composition_changed = Signal(object)
    autosave_requested = Signal(object)

    def __init__(
        self,
        composition: MotionComposition | None = None,
        parent=None,
        *,
        project_path: str | Path | None = None,
        standalone_document: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("MotionDesignerWindow")
        self._document_path = (
            Path(project_path).expanduser().resolve(strict=False)
            if project_path else None
        )
        self._managed_document = bool(standalone_document or project_path)
        self._document_dirty = False
        self._document_initializing = True
        self._composition_navigation: list[
            tuple[MotionComposition, str]
        ] = []
        if composition is None and self._document_path is not None:
            from app.motion_designer.project_io import load_motion_project

            composition = load_motion_project(self._document_path)
        self.setWindowTitle("Motion Designer")
        self.resize(1520, 900)
        self.setStyleSheet(MOTION_DESIGNER_QSS)
        self._selected_layer_id = ""
        self._time_ms = 0
        self._play_direction = 0
        self._loop_playback = False
        self._play_clock = QElapsedTimer()
        self._playback_fractional_ms = 0.0
        self._tracking_jobs: dict[str, tuple[QThread, MotionTrackingWorker, str]] = {}
        self._composition_tracking_job: tuple[
            QThread,
            MotionTrackingWorker | MotionFaceTrackingWorker,
            str,
            str,
        ] | None = None
        self._audio_analysis_job: tuple[QThread, MotionAudioAnalysisWorker] | None = None
        self._motion_export_job: tuple[QThread, MotionExportWorker] | None = None
        self._umg_generation_job: tuple[QThread, MotionUMGGenerationWorker] | None = None
        self._ai_generation_job: tuple[QThread, MotionAIGenerationWorker] | None = None
        self._ai_preview_job: tuple[QThread, MotionAICandidatePreviewWorker] | None = None
        self._ai_preview_pending: dict | None = None
        self._ai_patch_job: tuple[QThread, MotionAIPatchWorker] | None = None
        self.controller = MotionDocumentController(composition or MotionComposition(), self._on_model_changed)

        self.toolbar = MotionToolbar(self)
        self.addToolBar(self.toolbar)
        self.library = MotionLibraryPanel(self)
        self.layers = LayerPanel(self)
        self.media = QListWidget(self)
        self.audio = AudioReactivePanel(self)
        self.inspector = InspectorPanel(self)
        self.advanced = AdvancedMotionPanel(self)
        self.generator = GeneratorPanel(self)
        self.replicator = ReplicatorPanel(self)
        self.rig = RigPanel(self)
        self.puppet = PuppetPanel(self)
        self.image = ImagePanel(self)
        self.ar_pbr = ArPbrPanel(self)
        self.actor = ActorPanel(self)
        self.mmd = MMDPanel(self)
        self.vrm = VRMPanel(self)
        self.particle = ParticlePanel(self)
        self.vector = VectorPanel(self)
        self.typography = TypographyPanel(self)
        self.behaviors = BehaviorPanel(self)
        self.button = ButtonComponentPanel(self)
        self.effects = EffectMaskPanel("effect", self)
        self.craft = CraftStylePanel(self)
        self.masks = EffectMaskPanel("mask", self)
        self.tracking = TrackingPanel(self)
        self.inspector_tabs = QTabWidget(self)
        self.inspector_tabs.addTab(self.inspector, "Properties")
        self.inspector_tabs.addTab(self.advanced, "Motion")
        self.inspector_tabs.addTab(self.generator, "Generator")
        self.inspector_tabs.addTab(self.replicator, "Replicator")
        self.inspector_tabs.addTab(self.image, "Image")
        self.inspector_tabs.addTab(self.vector, "Shape")
        self.inspector_tabs.addTab(self.typography, "Text")
        self.inspector_tabs.addTab(self.behaviors, "Behaviors")
        self.inspector_tabs.addTab(self.effects, "Filters")
        self.inspector_tabs.addTab(self.masks, "Masks")
        self.inspector_tabs.addTab(self.ar_pbr, "3D")
        self.inspector_tabs.addTab(self.actor, "Actor")
        self.inspector_tabs.addTab(self.mmd, "MMD")
        self.inspector_tabs.addTab(self.vrm, "VRM")
        self.inspector_tabs.addTab(self.particle, "Particles")
        self.inspector_tabs.addTab(self.button, "Button")
        self.inspector_tabs.addTab(self.rig, "Rig")
        self.inspector_tabs.addTab(self.puppet, "Puppet")
        self.inspector_tabs.addTab(self.tracking, "Tracking")
        self.inspector_tabs.addTab(self.craft, "Craft")
        self.left_tabs = QTabWidget(self)
        self.left_tabs.addTab(self.library, "Add")
        self.left_tabs.addTab(self.inspector_tabs, "Inspector")
        self.project_tabs = QTabWidget(self)
        self.project_tabs.addTab(self.layers, "Layers")
        self.project_tabs.addTab(self.media, "Media")
        self.project_tabs.addTab(self.audio, "Audio")
        self.output = MotionOutputPanel(self)
        self.left_tabs.addTab(self.output, "Output")
        self.unreal_link_dialog = MotionUnrealLinkDialog(self)
        self.umg = self.unreal_link_dialog.panel

        self.canvas = MotionCanvas(self)
        self.preview = MotionPreviewWidget(self)
        self.viewer_tabs = QTabWidget(self)
        self.viewer_tabs.addTab(self.canvas, "Canvas")
        self.viewer_tabs.addTab(self.preview, "Preview")
        self.viewer_header = ViewerHeader(self)
        viewer = QWidget(self)
        viewer_layout = QVBoxLayout(viewer)
        viewer_layout.setContentsMargins(0, 0, 0, 0)
        viewer_layout.setSpacing(0)
        viewer_layout.addWidget(self.viewer_header)
        viewer_layout.addWidget(self.viewer_tabs, 1)
        self.timeline = MotionTimeline(self)
        self.project_and_viewer = QSplitter(Qt.Horizontal, self)
        self.project_and_viewer.setObjectName("MotionProjectAndViewer")
        self.project_and_viewer.addWidget(self.project_tabs)
        self.project_and_viewer.addWidget(viewer)
        self.project_and_viewer.setSizes([250, 1040])
        self.project_and_viewer.setStretchFactor(1, 1)
        self.project_and_viewer.setCollapsible(1, False)

        production = QSplitter(Qt.Vertical, self)
        production.setObjectName("MotionProductionStack")
        production.addWidget(self.project_and_viewer)
        production.addWidget(self.timeline)
        production.setSizes([560, 300])
        production.setCollapsible(0, False)
        workspace = QSplitter(Qt.Horizontal, self)
        workspace.setObjectName("MotionWorkspace")
        workspace.addWidget(self.left_tabs)
        workspace.addWidget(production)
        workspace.setSizes([310, 1290])
        workspace.setStretchFactor(1, 1)
        self.setCentralWidget(workspace)

        self.ai = MotionAIPanel(self)
        self.ai_dock = QDockWidget("AI", self)
        self.ai_dock.setObjectName("MotionAIDock")
        self.ai_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.ai_dock.setFeatures(
            QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetClosable
        )
        self.ai_dock.setWidget(self.ai)
        self.addDockWidget(Qt.RightDockWidgetArea, self.ai_dock)
        self.ai_dock.hide()

        self.toolbar.open_project_requested.connect(self._open_motion_project)
        self.toolbar.save_project_requested.connect(self._save_motion_project)
        self.toolbar.save_project_as_requested.connect(self._save_motion_project_as)
        self.toolbar.add_layer_requested.connect(self._add_layer)
        self.toolbar.behavior_requested.connect(self._add_behavior)
        self.toolbar.effect_requested.connect(self._add_effect)
        self.toolbar.replicator_requested.connect(self._create_replicator)
        self.toolbar.rig_requested.connect(self._open_rig)
        self.toolbar.component_requested.connect(
            lambda kind: (
                self._create_button_component()
                if kind == "button"
                else self._create_controller_null()
                if kind == "controller"
                else None
            )
        )
        self.toolbar.delete_requested.connect(self._delete_selected)
        self.toolbar.duplicate_requested.connect(self._duplicate_selected)
        self.toolbar.undo_requested.connect(self.controller.undo)
        self.toolbar.redo_requested.connect(self.controller.redo)
        self.toolbar.ai_toggled.connect(self.ai_dock.setVisible)
        self.toolbar.output_requested.connect(lambda: self.left_tabs.setCurrentWidget(self.output))
        self.toolbar.template_gallery_requested.connect(self._open_template_gallery)
        self.toolbar.unreal_link_requested.connect(self._open_unreal_link)
        self.toolbar.language_requested.connect(self.set_ui_language)
        self.toolbar.workspace_panel_requested.connect(self._show_workspace_panel)
        self.toolbar.precompose_requested.connect(self._precompose_selected)
        self.toolbar.time_remap_requested.connect(self._apply_time_remap_preset)
        self.toolbar.navigate_parent_requested.connect(
            self._navigate_to_parent_composition,
        )
        self.ai_dock.visibilityChanged.connect(self.toolbar.set_ai_visible)
        self.layers.layer_selected.connect(self._select_layer)
        self.layers.layer_activated.connect(self._open_layer_in_place)
        self.layers.layer_flags_changed.connect(self._update_layer_flags)
        self.layers.layer_structure_changed.connect(self.controller.apply_layer_structure)
        self.canvas.layer_selected.connect(self._select_layer)
        self.canvas.layer_moved.connect(self._move_layer)
        self.canvas.rig_bone_moved.connect(self._move_rig_bone)
        self.canvas.rig_bone_selected.connect(self._select_rig_bone)
        self.canvas.puppet_pin_moved.connect(self.controller.move_puppet_pin)
        self.canvas.puppet_pin_selected.connect(self._select_puppet_pin)
        self.canvas.vector_path_changed.connect(self._set_vector_path)
        self.canvas.typography_path_changed.connect(self._set_typography_path)
        self.canvas.typography_path_offset_changed.connect(self._set_typography_path_offset)
        self.inspector.property_changed.connect(self._set_inspector_property)
        self.inspector.keyframe_requested.connect(self._set_keyframe)
        self.advanced.metadata_changed.connect(self._set_advanced_metadata)
        self.generator.source_changed.connect(self._set_generator_params)
        self.replicator.settings_changed.connect(self._set_replicator_params)
        self.rig.bone_changed.connect(self.controller.update_rig_bone)
        self.rig.bone_selected.connect(self.timeline.set_selected_rig_bone)
        self.rig.mirror_requested.connect(self.controller.mirror_rig_bone)
        self.rig.ik_lock_requested.connect(self.controller.create_rig_ik_lock)
        self.rig.constraint_enabled.connect(
            self.controller.set_rig_constraint_enabled,
        )
        self.rig.constraint_bake_requested.connect(
            self.controller.bake_rig_constraint,
        )
        self.puppet.mesh_create_requested.connect(
            self.controller.create_puppet_mesh,
        )
        self.puppet.mesh_settings_changed.connect(
            self.controller.configure_puppet_tear_repair,
        )
        self.puppet.pin_add_requested.connect(self.controller.add_puppet_pin)
        self.puppet.pin_changed.connect(self.controller.update_puppet_pin)
        self.image.source_changed.connect(self._set_image_params)
        self.image.keyframe_requested.connect(self._set_image_keyframe)
        self.vector.source_changed.connect(self._set_vector_params)
        self.typography.source_changed.connect(self._set_typography_params)
        self.library.apply_requested.connect(self._apply_library_item)
        self.library.templates_requested.connect(self._open_template_gallery)
        self.library.ai_requested.connect(self._show_ai_workspace)
        self.behaviors.add_requested.connect(self._add_behavior)
        self.behaviors.delete_requested.connect(self._delete_behavior)
        self.behaviors.parameter_changed.connect(self._set_behavior_param)
        self.button.create_requested.connect(self._create_button_component)
        self.button.remove_requested.connect(self._remove_button_component)
        self.button.state_changed.connect(self._set_button_state)
        self.button.settings_changed.connect(self._update_button_component)
        self.effects.add_requested.connect(self._add_effect)
        self.effects.delete_requested.connect(self._delete_effect)
        self.effects.parameter_changed.connect(self._set_effect_param)
        self.effects.keyframe_toggled.connect(self._toggle_effect_keyframe)
        self.effects.adjustment_scope_changed.connect(
            self._set_adjustment_scope
        )
        self.effects.effect_group_scope_changed.connect(
            self._set_effect_group_scope
        )
        self.craft.apply_requested.connect(self._apply_craft_style)
        self.craft.clear_requested.connect(self._clear_craft_style)
        self.craft.texture_requested.connect(self._attach_craft_texture)
        self.masks.add_requested.connect(self._add_mask)
        self.masks.delete_requested.connect(self._delete_mask)
        self.masks.parameter_changed.connect(self._set_mask_param)
        self.masks.keyframe_toggled.connect(self._toggle_mask_keyframe)
        self.masks.item_changed.connect(self._set_mask_item)
        self.masks.tracking_requested.connect(self._start_mask_tracking)
        self.masks.tracking_cancel_requested.connect(self._cancel_mask_tracking)
        self.tracking.apply_requested.connect(self._apply_composition_track)
        self.tracking.analyze_requested.connect(
            self._start_composition_tracking
        )
        self.tracking.corner_pin_requested.connect(
            self._apply_composition_track_to_corner_pin
        )
        self.tracking.relink_requested.connect(self._relink_composition_track)
        self.ar_pbr.source_changed.connect(self._set_ar_pbr_params)
        self.actor.source_changed.connect(self._set_actor_params)
        self.mmd.source_changed.connect(self._set_mmd_params)
        self.vrm.source_changed.connect(self._set_vrm_params)
        self.particle.source_changed.connect(self._set_particle_params)
        self.timeline.time_changed.connect(self._set_time)
        self.timeline.playback_requested.connect(self._set_playback_direction)
        self.timeline.loop_changed.connect(self._set_loop_playback)
        self.timeline.layer_selected.connect(self._select_layer)
        self.timeline.layer_timing_changed.connect(self._set_layer_timing)
        self.timeline.keyframe_changed.connect(self.controller.update_keyframe)
        self.timeline.rig_keyframe_changed.connect(
            self.controller.update_rig_keyframe,
        )
        self.timeline.puppet_keyframe_changed.connect(
            self.controller.update_puppet_keyframe,
        )
        self.timeline.keyframe_tangent_requested.connect(
            self.controller.update_keyframe_tangent,
        )
        self.timeline.keyframe_roving_requested.connect(
            self.controller.set_keyframe_roving,
        )
        self.timeline.keyframe_tangent_value_requested.connect(
            self.controller.update_keyframe_tangent_value,
        )
        self.timeline.expression_link_requested.connect(
            self._open_expression_link,
        )
        self.viewer_header.zoom_changed.connect(self.canvas.set_zoom_mode)
        self.viewer_header.grid_changed.connect(self.canvas.set_grid_visible)
        self.viewer_header.safe_changed.connect(self.canvas.set_safe_guides_visible)
        self.ai.plan_requested.connect(self._plan_ai_request)
        self.ai.apply_requested.connect(self._apply_ai_proposal)
        self.ai.patch_requested.connect(self._plan_ai_patch)
        self.ai.patch_apply_requested.connect(self._apply_ai_patch)
        self.ai.decomposition_repaired.connect(self._repair_ai_decomposition)
        self.audio.analyze_requested.connect(self._start_audio_analysis)
        self.audio.bind_requested.connect(self._bind_audio_reactive)
        self.audio.bake_requested.connect(self._bake_audio_reactive)
        self.output.color_settings_changed.connect(self._set_motion_color_settings)
        self.output.export_requested.connect(self._start_motion_export)
        self.output.cancel_requested.connect(self._cancel_motion_export)
        self.umg.generate_requested.connect(self._start_umg_generation)
        self.umg.cancel_requested.connect(self._cancel_umg_generation)
        self._play_timer = QTimer(self)
        self._play_timer.setInterval(16)
        self._play_timer.timeout.connect(self._tick)
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(30000)
        self._autosave_timer.timeout.connect(self._autosave_document)
        self._autosave_timer.start()
        self._on_model_changed(self.controller.composition)
        self._document_initializing = False
        self._document_dirty = False
        self.set_ui_language(current_language(), persist=False)
        self._update_document_title()

    def set_ui_language(self, language: str, *, persist: bool = True) -> str:
        code = str(language or "").split("_", 1)[0].lower()
        from app.i18n import SUPPORTED_LANGUAGES

        if code not in SUPPORTED_LANGUAGES:
            raise ValueError(f"Unsupported Motion Designer language: {language}")
        set_language(code)
        if persist:
            save_language(code)
        self.toolbar.rebuild_language_menu(code)
        retranslate_motion_ui(self, code)
        self._update_document_title()
        return code

    def _on_model_changed(self, composition: MotionComposition) -> None:
        self.canvas.set_composition(composition, self._time_ms)
        self.preview.set_composition(composition, self._time_ms)
        self.layers.set_composition(composition)
        self.timeline.set_composition(composition, self._time_ms)
        self.viewer_header.set_fps(composition.fps)
        self._update_media_panel(composition)
        self.audio.set_composition(composition)
        self.output.set_composition(composition)
        self.umg.set_composition(composition)
        selected = next(
            (layer for layer in composition.layers if layer.id == self._selected_layer_id),
            None,
        )
        self.rig.set_layer(selected, composition)
        self.tracking.set_context(composition, selected)
        self.composition_changed.emit(composition)
        if not self._document_initializing:
            self._document_dirty = True
            self._update_document_title()
        if self._selected_layer_id:
            self._select_layer(self._selected_layer_id)

    def _update_document_title(self) -> None:
        name = (
            self._document_path.name
            if self._document_path is not None
            else self.controller.composition.name or "Untitled"
        )
        breadcrumb = " / ".join(
            [
                *(parent.name for parent, _layer_id in self._composition_navigation),
                self.controller.composition.name,
            ],
        )
        dirty = " *" if self._document_dirty else ""
        self.setWindowTitle(
            f"{motion_text('Motion Designer')} - {name} - {breadcrumb}{dirty}",
        )

    def _root_composition_snapshot(self) -> MotionComposition:
        from app.motion_designer.precomposition import set_embedded_composition

        child = MotionComposition.from_dict(
            self.controller.composition.to_dict(),
        )
        for parent_source, layer_id in reversed(self._composition_navigation):
            parent = MotionComposition.from_dict(parent_source.to_dict())
            layer = next(
                (row for row in parent.layers if row.id == layer_id),
                None,
            )
            if layer is None:
                raise ValueError(
                    f"Missing parent pre-compose layer: {layer_id}",
                )
            set_embedded_composition(layer, child)
            parent.revision += 1
            child = parent
        return child

    def _confirm_discard_document_changes(self) -> bool:
        if not self._managed_document or not self._document_dirty:
            return True
        answer = QMessageBox.question(
            self,
            motion_text("Unsaved Motion Project"),
            motion_text("Save changes to the current Motion project?"),
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if answer == QMessageBox.StandardButton.Cancel:
            return False
        if answer == QMessageBox.StandardButton.Save:
            return self._save_motion_project()
        return True

    def _open_motion_project(self) -> bool:
        if not self._confirm_discard_document_changes():
            return False
        from app.motion_designer.project_io import (
            MOTION_PROJECT_FILTER,
            load_motion_project,
        )

        path, _ = QFileDialog.getOpenFileName(
            self, motion_text("Open Motion Project"), "", MOTION_PROJECT_FILTER,
        )
        if not path:
            return False
        try:
            composition = load_motion_project(path)
        except Exception as exc:
            QMessageBox.critical(self, motion_text("Open Motion Project"), str(exc))
            return False
        self._managed_document = True
        self._document_path = Path(path).expanduser().resolve(strict=False)
        self._selected_layer_id = ""
        self._time_ms = 0
        self._composition_navigation.clear()
        self.toolbar.set_parent_navigation_enabled(False)
        self.controller.load(composition)
        self._document_dirty = False
        self._update_document_title()
        self.statusBar().showMessage(
            motion_text("Opened {name}", name=self._document_path.name),
            5000,
        )
        return True

    def _save_motion_project(self) -> bool:
        if self._document_path is None:
            return self._save_motion_project_as()
        from app.motion_designer.project_io import save_motion_project

        try:
            self._document_path = save_motion_project(
                self._root_composition_snapshot(),
                self._document_path,
            )
        except Exception as exc:
            QMessageBox.critical(self, motion_text("Save Motion Project"), str(exc))
            return False
        self._managed_document = True
        self._document_dirty = False
        self._remove_document_recovery()
        self._update_document_title()
        self.statusBar().showMessage(
            motion_text("Saved {name}", name=self._document_path.name),
            5000,
        )
        return True

    def _save_motion_project_as(self) -> bool:
        from app.motion_designer.project_io import MOTION_PROJECT_FILTER

        initial = str(self._document_path or Path(
            f"{self.controller.composition.name or 'motion_project'}.tgmotion"
        ))
        path, _ = QFileDialog.getSaveFileName(
            self, motion_text("Save Motion Project"), initial, MOTION_PROJECT_FILTER,
        )
        if not path:
            return False
        self._document_path = Path(path).expanduser().resolve(strict=False)
        return self._save_motion_project()

    def _document_recovery_path(self) -> Path:
        from app.motion_designer.recovery import (
            default_motion_recovery_root,
            motion_recovery_path,
        )

        root = default_motion_recovery_root(self._document_path)
        return motion_recovery_path(root, self.controller.composition.id)

    def _remove_document_recovery(self) -> None:
        try:
            self._document_recovery_path().unlink(missing_ok=True)
        except OSError:
            pass

    def _autosave_document(self) -> None:
        composition = self._root_composition_snapshot()
        self.autosave_requested.emit(composition)
        if not self._managed_document or not self._document_dirty:
            return
        from app.motion_designer.recovery import write_motion_recovery

        try:
            write_motion_recovery(
                composition,
                self._document_recovery_path(),
                project_path=self._document_path,
            )
        except Exception as exc:
            self.statusBar().showMessage(f"Motion autosave failed: {exc}", 5000)

    def _open_rig(self, rig_kind: str) -> None:
        kind = str(rig_kind)
        if kind == "full_body":
            dialog = FullBodyRigDialog(
                self.controller.composition,
                selected_layer_id=self._selected_layer_id,
                parent=self,
            )
            retranslate_motion_ui(dialog, current_language())
            if dialog.exec() == QDialog.Accepted:
                candidate = MotionComposition.from_dict(
                    self.controller.composition.to_dict()
                )
                rig = dialog.create(candidate)
                self.controller.replace(candidate)
                if rig.bindings:
                    self._select_layer(rig.bindings[0].layer_id)
                    self.inspector_tabs.setCurrentWidget(self.rig)
            return
        if kind != "arm_wave":
            return
        if len(self.controller.composition.layers) < 4:
            return
        dialog = CutoutArmRigDialog(self.controller.composition, self)
        retranslate_motion_ui(dialog, current_language())
        if dialog.exec() == QDialog.Accepted:
            self.controller.replace(dialog.result_composition())

    def _open_unreal_link(self) -> None:
        self.umg.set_composition(self.controller.composition)
        retranslate_motion_ui(self.unreal_link_dialog, current_language())
        self.unreal_link_dialog.show()
        self.unreal_link_dialog.raise_()
        self.unreal_link_dialog.activateWindow()

    def _precompose_selected(self) -> None:
        layer_ids = self.layers.selected_layer_ids()
        if not layer_ids and self._selected_layer_id:
            layer_ids = [self._selected_layer_id]
        if not layer_ids:
            return
        from app.motion_designer.precomposition import create_precomposition

        candidate = MotionComposition.from_dict(
            self.controller.composition.to_dict(),
        )
        _child, layer = create_precomposition(
            candidate,
            layer_ids,
            name="Pre-compose",
        )
        self.controller.replace(candidate)
        self._select_layer(layer.id)

    def _apply_time_remap_preset(self, preset: str) -> None:
        if not self._selected_layer_id:
            return
        if str(preset).startswith("blend:"):
            from app.motion_designer.frame_blending import (
                frame_blending_preflight,
                set_layer_frame_blending,
            )

            candidate = MotionComposition.from_dict(
                self.controller.composition.to_dict(),
            )
            layer = find_layer(candidate, self._selected_layer_id)
            set_layer_frame_blending(layer, str(preset).split(":", 1)[1])
            candidate.revision += 1
            self.controller.replace(candidate)
            report = frame_blending_preflight(layer)
            if str(report.get("fallback_reason") or ""):
                self.statusBar().showMessage(
                    "Optical Flow is not active; using deterministic Frame Mix.",
                    5000,
                )
            return
        from app.motion_designer.time_remap import (
            apply_time_remap_preset,
            clear_layer_time_remap,
        )

        candidate = MotionComposition.from_dict(
            self.controller.composition.to_dict(),
        )
        layer = find_layer(candidate, self._selected_layer_id)
        if str(preset) == "clear":
            if not clear_layer_time_remap(layer):
                return
        else:
            apply_time_remap_preset(layer, str(preset))
        candidate.revision += 1
        self.controller.replace(candidate)
        self.timeline.set_selected_layer(layer.id)
        for index in range(self.timeline.graph_properties.count()):
            item = self.timeline.graph_properties.item(index)
            if str(item.data(Qt.UserRole) or "") == "time_remap":
                self.timeline.graph_properties.setCurrentItem(item)
                break

    def _open_expression_link(
        self,
        target_layer_id: str,
        target_property: str,
    ) -> None:
        from app.motion_designer.expressions import set_layer_expression
        from app.motion_designer.ui.expression_link_dialog import (
            ExpressionLinkDialog,
        )

        dialog = ExpressionLinkDialog(
            self.controller.composition,
            target_layer_id,
            target_property,
            self,
        )
        retranslate_motion_ui(dialog, current_language())
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if not dialog.source_layer_id or not dialog.source_property_name:
            return
        candidate = MotionComposition.from_dict(
            self.controller.composition.to_dict(),
        )
        target = find_layer(candidate, target_layer_id)
        set_layer_expression(
            target,
            target_property,
            {
                "op": "property",
                "layer_id": dialog.source_layer_id,
                "property": dialog.source_property_name,
            },
        )
        candidate.revision += 1
        self.controller.replace(candidate)

    def _open_layer_in_place(self, layer_id: str) -> None:
        from app.motion_designer.precomposition import embedded_composition

        parent = self.controller.composition
        layer = next(
            (row for row in parent.layers if row.id == str(layer_id)),
            None,
        )
        child = embedded_composition(layer) if layer is not None else None
        if child is None:
            return
        self._composition_navigation.append((
            MotionComposition.from_dict(parent.to_dict()),
            layer.id,
        ))
        self.controller.load(child)
        self.toolbar.set_parent_navigation_enabled(True)
        self._selected_layer_id = ""
        self._set_time(0)
        self.timeline.set_time(0)
        self._update_document_title()

    def _navigate_to_parent_composition(self) -> None:
        if not self._composition_navigation:
            return
        from app.motion_designer.precomposition import set_embedded_composition

        child = MotionComposition.from_dict(
            self.controller.composition.to_dict(),
        )
        parent, layer_id = self._composition_navigation.pop()
        layer = next(
            (row for row in parent.layers if row.id == layer_id),
            None,
        )
        if layer is None:
            raise ValueError(f"Missing parent pre-compose layer: {layer_id}")
        set_embedded_composition(layer, child)
        parent.revision += 1
        self.controller.load(parent)
        self.toolbar.set_parent_navigation_enabled(
            bool(self._composition_navigation),
        )
        self._select_layer(layer.id)
        self._update_document_title()

    def _open_template_gallery(self) -> None:
        from app.motion_designer.templates import (
            apply_template_to_composition,
            recommended_variant,
        )

        composition = self.controller.composition
        dialog = MotionTemplateGalleryDialog(
            self,
            variant=recommended_variant(composition.width, composition.height),
        )
        retranslate_motion_ui(dialog, current_language())
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        template_id = dialog.selected_template_id
        if not template_id:
            return
        candidate = apply_template_to_composition(
            composition,
            template_id,
            variant=dialog.selected_variant,
            replace_existing=True,
        )
        instance_id = str(
            candidate.metadata["last_applied_template"]["template_instance_id"]
        )
        added = [
            layer
            for layer in candidate.layers
            if layer.metadata.get("template_instance_id") == instance_id
        ]
        self.controller.replace(candidate)
        self._restart_template_playback()
        if added:
            self._select_layer(added[-1].id)

    def _show_ai_workspace(self) -> None:
        self.ai_dock.show()
        self.ai_dock.raise_()
        self.toolbar.set_ai_visible(True)
        self.ai.prompt.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def _show_workspace_panel(self, panel: str) -> None:
        requested = str(panel or "").lower()
        if requested == "library":
            self.left_tabs.setCurrentWidget(self.library)
            return
        if requested == "inspector":
            self.left_tabs.setCurrentWidget(self.inspector_tabs)
            return
        if requested == "project":
            visible = self.project_tabs.isVisible()
            self.project_tabs.setVisible(not visible)
            if not visible:
                self.project_and_viewer.setSizes([250, max(1, self.width() - 560)])

    def _add_layer(self, layer_type: str) -> None:
        composition = self.controller.composition
        requested_type = str(layer_type or "shape").lower()
        if requested_type == "generator" or requested_type.startswith("generator:"):
            from app.motion_designer.generators import create_generator_layer

            kind = requested_type.partition(":")[2] or "gradient"
            layer = create_generator_layer(
                kind,
                width=composition.width,
                height=composition.height,
                duration_ms=composition.duration_ms,
            )
            self.controller.add_layer(layer)
            self._select_layer(layer.id)
            self.left_tabs.setCurrentWidget(self.inspector_tabs)
            self.inspector_tabs.setCurrentWidget(self.generator)
            return
        if requested_type == "ar_pbr":
            uri, _ = QFileDialog.getOpenFileName(
                self, "Open 3D object", "", "3D Objects (*.gltf *.glb *.fbx *.obj *.vrm *.usd *.usdz *.arpbr)",
            )
            if not uri:
                return
            from app.motion_designer.ar_pbr_source import create_ar_pbr_layer

            layer = create_ar_pbr_layer(
                uri, width=composition.width, height=composition.height,
                duration_ms=composition.duration_ms, name=Path(uri).stem,
            )
            self.controller.add_layer(layer)
            self._select_layer(layer.id)
            self.left_tabs.setCurrentWidget(self.inspector_tabs)
            self.inspector_tabs.setCurrentWidget(self.ar_pbr)
            return
        if requested_type in {"live2d_actor", "spine_actor"}:
            if requested_type == "live2d_actor":
                title = "Open Live2D actor"
                file_filter = "Live2D Models (*.model3.json *.model3.json.bytes *.unitypackage)"
            else:
                title = "Open Spine actor"
                file_filter = "Spine Models (*.json *.skel *.atlas)"
            uri, _ = QFileDialog.getOpenFileName(self, title, "", file_filter)
            if not uri:
                return
            from app.motion_designer.actor_source import create_actor_layer

            layer = create_actor_layer(
                requested_type, uri, width=composition.width, height=composition.height,
                duration_ms=composition.duration_ms, name=Path(uri).stem,
            )
            self.controller.add_layer(layer)
            self._select_layer(layer.id)
            self.left_tabs.setCurrentWidget(self.inspector_tabs)
            self.inspector_tabs.setCurrentWidget(self.actor)
            return
        if requested_type == "mmd_actor":
            model_path, _ = QFileDialog.getOpenFileName(
                self, "Open MMD model", "", "MMD Models (*.pmx *.pmd *.pbx.json)",
            )
            if not model_path:
                return
            motion_path, _ = QFileDialog.getOpenFileName(
                self, "Choose VMD motion", str(Path(model_path).parent), "VMD Motion (*.vmd)",
            )
            from app.motion_designer.mmd_source import create_mmd_layer

            layer = create_mmd_layer(
                model_path, motion_path=motion_path or None,
                width=composition.width, height=composition.height,
                duration_ms=composition.duration_ms, name=Path(model_path).stem,
            )
            self.controller.add_layer(layer)
            self._select_layer(layer.id)
            self.left_tabs.setCurrentWidget(self.inspector_tabs)
            self.inspector_tabs.setCurrentWidget(self.mmd)
            return
        if requested_type == "vrm_actor":
            avatar_path, _ = QFileDialog.getOpenFileName(
                self, "Open VRM avatar", "", "VRM Avatar (*.vrm)",
            )
            if not avatar_path:
                return
            from app.motion_designer.vrm_source import create_vrm_layer

            layer = create_vrm_layer(
                avatar_path, width=composition.width, height=composition.height,
                duration_ms=composition.duration_ms, name=Path(avatar_path).stem,
            )
            self.controller.add_layer(layer)
            self._select_layer(layer.id)
            self.left_tabs.setCurrentWidget(self.inspector_tabs)
            self.inspector_tabs.setCurrentWidget(self.vrm)
            return
        if requested_type == "camera":
            from app.motion_designer.ar_pbr_source import create_camera_layer

            layer = create_camera_layer(duration_ms=composition.duration_ms)
            self.controller.add_layer(layer)
            self._select_layer(layer.id)
            self.left_tabs.setCurrentWidget(self.inspector_tabs)
            self.inspector_tabs.setCurrentWidget(self.ar_pbr)
            return
        if requested_type == "light":
            from app.motion_designer.ar_pbr_source import create_light_layer

            layer = create_light_layer(duration_ms=composition.duration_ms)
            self.controller.add_layer(layer)
            self._select_layer(layer.id)
            self.left_tabs.setCurrentWidget(self.inspector_tabs)
            self.inspector_tabs.setCurrentWidget(self.ar_pbr)
            return
        if requested_type == "particle":
            from app.motion_designer.particles import create_particle_layer

            layer = create_particle_layer(
                width=composition.width, height=composition.height,
                duration_ms=composition.duration_ms,
            )
            self.controller.add_layer(layer)
            self._select_layer(layer.id)
            self.left_tabs.setCurrentWidget(self.inspector_tabs)
            self.inspector_tabs.setCurrentWidget(self.particle)
            return
        layer_type = "shape" if requested_type in {
            "shape", "rectangle", "ellipse", "polygon", "star", "path",
        } else requested_type
        uri = ""
        params = {"width": 420, "height": 240, "fill": "#3f8fba"}
        if layer_type == "text":
            params = {"text": "Title", "font_size": 72, "fill": "#16191e"}
        elif layer_type == "image":
            uri, _ = QFileDialog.getOpenFileName(self, "Open image", "", "Images (*.png *.jpg *.jpeg *.webp)")
            if not uri:
                return
        elif layer_type == "line":
            params = {"width": 520, "stroke_width": 5, "fill": "#3f8fba"}
        elif requested_type in {"rectangle", "ellipse", "polygon", "star"}:
            params = {
                "width": 360, "height": 360, "fill": "#3f8fba",
                "stroke": "#20242b", "stroke_width": 3, "shape": requested_type,
                "sides": 5, "inner_ratio": .45,
            }
        elif requested_type == "path":
            params = {
                "width": 520, "height": 280, "fill": "#00000000",
                "stroke": "#3f8fba", "stroke_width": 6, "cap": "round",
                "shape": "path", "path": default_pen_path(520, 280).to_dict(),
            }
        layer = MotionLayer(name=requested_type.title(), layer_type=layer_type,
                            source=SourceRef(kind=layer_type, uri=uri, params=params), out_ms=composition.duration_ms)
        layer.transform.position.default = [composition.width * .5, composition.height * .5]
        self.controller.add_layer(layer)
        self._select_layer(layer.id)

    def _select_layer(self, layer_id: str) -> None:
        previous_layer_id = self._selected_layer_id
        self._selected_layer_id = str(layer_id or "")
        layer = next((item for item in self.controller.composition.layers if item.id == self._selected_layer_id), None)
        self.inspector.set_layer(layer)
        self.advanced.set_layer(layer, self.controller.composition)
        self.generator.set_layer(layer)
        self.replicator.set_layer(layer)
        self.rig.set_layer(layer, self.controller.composition)
        self.puppet.set_layer(layer)
        self.image.set_layer(
            layer,
            max(0, self._time_ms - layer.in_ms) if layer is not None else 0,
        )
        self.vector.set_layer(layer, self.controller.composition)
        self.typography.set_layer(layer)
        self.behaviors.set_layer(layer)
        self.effects.set_context(layer, self.controller.composition)
        self.craft.set_layer(layer)
        self.masks.set_layer(layer)
        local_time = self._layer_local_time(layer)
        self.effects.set_time(local_time)
        self.masks.set_time(local_time)
        self.tracking.set_context(self.controller.composition, layer)
        self.audio.set_layer(layer)
        self.ar_pbr.set_layer(layer)
        self.actor.set_layer(layer)
        self.mmd.set_layer(layer)
        self.vrm.set_layer(layer)
        self.particle.set_layer(layer)
        self.button.set_layer(layer)
        self.timeline.set_selected_layer(self._selected_layer_id)
        self.canvas.set_selected_layer(self._selected_layer_id)
        if layer is not None:
            self.layers.select_layer(layer.id)
            if (
                previous_layer_id != layer.id
                or self.left_tabs.currentWidget() is self.library
            ):
                self.left_tabs.setCurrentWidget(self.inspector_tabs)
                self.inspector_tabs.setCurrentWidget(
                    self._preferred_inspector_for_layer(layer)
                )
        elif self.left_tabs.currentWidget() is self.inspector_tabs:
            self.left_tabs.setCurrentWidget(self.library)

    def _preferred_inspector_for_layer(self, layer: MotionLayer) -> QWidget:
        layer_type = str(layer.layer_type or "").lower()
        if layer_type == "text":
            return self.typography
        if layer_type == "generator":
            return self.generator
        if layer_type == "image":
            return self.image
        if layer_type in {"shape", "polygon", "star", "path", "line"}:
            return self.vector
        if layer_type in {"live2d_actor", "spine_actor"}:
            return self.actor
        if layer_type == "mmd_actor":
            return self.mmd
        if layer_type == "vrm_actor":
            return self.vrm
        if layer_type in {"ar_pbr", "camera", "light"}:
            return self.ar_pbr
        if layer_type == "particle":
            return self.particle
        return self.inspector

    def _create_replicator(self) -> None:
        if not self._selected_layer_id:
            return
        self._set_replicator_params({
            "enabled": True,
            "arrangement": "line",
            "count": 5,
            "columns": 5,
            "offset": [80.0, 0.0],
            "rotation": 0.0,
            "scale": [1.0, 1.0],
            "opacity_start": 1.0,
            "opacity_end": 1.0,
            "jitter": [0.0, 0.0],
            "seed": 0,
        })
        self.left_tabs.setCurrentWidget(self.inspector_tabs)
        self.inspector_tabs.setCurrentWidget(self.replicator)

    def _create_button_component(self) -> None:
        if not self._selected_layer_id:
            return
        from app.motion_designer.interactive_button import create_button_component

        candidate = MotionComposition.from_dict(self.controller.composition.to_dict())
        layer = find_layer(candidate, self._selected_layer_id)
        create_button_component(layer)
        candidate.revision += 1
        self.controller.replace(candidate)
        self.left_tabs.setCurrentWidget(self.inspector_tabs)
        self.inspector_tabs.setCurrentWidget(self.button)

    def _create_controller_null(self) -> None:
        from app.motion_designer.controllers import create_controller_layer

        candidate = MotionComposition.from_dict(
            self.controller.composition.to_dict(),
        )
        layer = create_controller_layer(candidate)
        self.controller.replace(candidate)
        self._select_layer(layer.id)

    def _remove_button_component(self) -> None:
        if not self._selected_layer_id:
            return
        from app.motion_designer.interactive_button import remove_button_component

        candidate = MotionComposition.from_dict(self.controller.composition.to_dict())
        layer = find_layer(candidate, self._selected_layer_id)
        if not remove_button_component(layer):
            return
        candidate.revision += 1
        self.controller.replace(candidate)

    def _set_button_state(self, state: str) -> None:
        self._update_button_component({"active_state": str(state)})

    def _update_button_component(self, changes: object) -> None:
        if not self._selected_layer_id or not isinstance(changes, dict):
            return
        from app.motion_designer.interactive_button import (
            button_component,
            set_button_component,
            update_button_component_data,
        )

        candidate = MotionComposition.from_dict(self.controller.composition.to_dict())
        layer = find_layer(candidate, self._selected_layer_id)
        component = button_component(layer)
        if component is None:
            return
        update_button_component_data(component, changes)
        set_button_component(layer, component)
        candidate.revision += 1
        self.controller.replace(candidate)

    def _set_ar_pbr_params(self, changes: object) -> None:
        if not self._selected_layer_id or not isinstance(changes, dict):
            return
        from app.motion_designer.ar_pbr_source import set_source_defaults

        candidate = MotionComposition.from_dict(self.controller.composition.to_dict())
        layer = find_layer(candidate, self._selected_layer_id)
        if layer.layer_type not in {"ar_pbr", "camera", "light"}:
            return
        set_source_defaults(layer.source.params, changes)
        candidate.revision += 1
        self.controller.replace(candidate)

    def _set_actor_params(self, changes: object) -> None:
        if not self._selected_layer_id or not isinstance(changes, dict):
            return
        from app.motion_designer.actor_source import ACTOR_SOURCE_KINDS, update_actor_params

        candidate = MotionComposition.from_dict(self.controller.composition.to_dict())
        layer = find_layer(candidate, self._selected_layer_id)
        if layer.layer_type not in ACTOR_SOURCE_KINDS:
            return
        update_actor_params(layer, changes)
        candidate.revision += 1
        self.controller.replace(candidate)

    def _set_mmd_params(self, changes: object) -> None:
        if not self._selected_layer_id or not isinstance(changes, dict):
            return
        from app.motion_designer.mmd_source import MMD_SOURCE_KIND, update_mmd_params

        candidate = MotionComposition.from_dict(self.controller.composition.to_dict())
        layer = find_layer(candidate, self._selected_layer_id)
        if layer.layer_type != MMD_SOURCE_KIND:
            return
        update_mmd_params(layer, changes)
        candidate.revision += 1
        self.controller.replace(candidate)

    def _set_vrm_params(self, changes: object) -> None:
        if not self._selected_layer_id or not isinstance(changes, dict):
            return
        from app.motion_designer.vrm_source import VRM_SOURCE_KIND, update_vrm_params

        candidate = MotionComposition.from_dict(self.controller.composition.to_dict())
        layer = find_layer(candidate, self._selected_layer_id)
        if layer.layer_type != VRM_SOURCE_KIND:
            return
        update_vrm_params(layer, changes)
        candidate.revision += 1
        self.controller.replace(candidate)

    def _set_particle_params(self, changes: object) -> None:
        if not self._selected_layer_id or not isinstance(changes, dict):
            return
        from app.motion_designer.particles import PARTICLE_SOURCE_KIND, update_particle_params

        candidate = MotionComposition.from_dict(self.controller.composition.to_dict())
        layer = find_layer(candidate, self._selected_layer_id)
        if layer.layer_type != PARTICLE_SOURCE_KIND:
            return
        values = dict(changes)
        blend_mode = str(values.pop("__blend_mode", layer.blend_mode))
        update_particle_params(layer, values)
        layer.blend_mode = blend_mode
        candidate.revision += 1
        self.controller.replace(candidate)

    def _set_advanced_metadata(self, changes: object) -> None:
        if not self._selected_layer_id or not isinstance(changes, dict):
            return
        candidate = MotionComposition.from_dict(self.controller.composition.to_dict())
        layer = find_layer(candidate, self._selected_layer_id)
        layer.metadata.update(deepcopy(changes))
        candidate.revision += 1
        self.controller.replace(candidate)

    def _set_generator_params(self, changes: object) -> None:
        if not self._selected_layer_id or not isinstance(changes, dict):
            return
        from app.motion_designer.generators import (
            GENERATOR_SOURCE_KIND,
            update_generator_params,
        )

        candidate = MotionComposition.from_dict(self.controller.composition.to_dict())
        layer = find_layer(candidate, self._selected_layer_id)
        if layer.layer_type != GENERATOR_SOURCE_KIND:
            return
        update_generator_params(layer, changes)
        candidate.revision += 1
        self.controller.replace(candidate)

    def _set_replicator_params(self, changes: object) -> None:
        if not self._selected_layer_id or not isinstance(changes, dict):
            return
        candidate = MotionComposition.from_dict(self.controller.composition.to_dict())
        layer = find_layer(candidate, self._selected_layer_id)
        if layer.layer_type in {"group", "null", "camera", "light", "adjustment"}:
            return
        layer.metadata["replicator"] = deepcopy(changes)
        candidate.revision += 1
        self.controller.replace(candidate)

    def _apply_library_item(self, domain: str, kind: str) -> None:
        if domain == "object":
            self._add_layer(kind)
        elif domain == "generator":
            self._add_layer(f"generator:{kind}")
        elif domain == "replicator":
            if not self._selected_layer_id:
                return
            self._create_replicator()
            layer = find_layer(self.controller.composition, self._selected_layer_id)
            current = layer.metadata.get("replicator")
            current = dict(current) if isinstance(current, dict) else {}
            self._set_replicator_params({
                **current,
                "enabled": True,
                "arrangement": kind,
            })
        elif domain == "behavior":
            self._add_behavior(kind)
            self.left_tabs.setCurrentWidget(self.inspector_tabs)
            self.inspector_tabs.setCurrentWidget(self.behaviors)
        elif domain == "effect":
            self._add_effect(kind)
            self.left_tabs.setCurrentWidget(self.inspector_tabs)
            self.inspector_tabs.setCurrentWidget(self.effects)
        elif domain == "template":
            from app.motion_designer.templates import apply_template_to_composition

            candidate = apply_template_to_composition(
                self.controller.composition,
                kind,
                replace_existing=True,
            )
            instance_id = str(
                candidate.metadata["last_applied_template"][
                    "template_instance_id"
                ]
            )
            added = [
                layer
                for layer in candidate.layers
                if layer.metadata.get("template_instance_id") == instance_id
            ]
            self.controller.replace(candidate)
            self._restart_template_playback()
            if added:
                self._select_layer(added[-1].id)
        elif domain == "advanced_preset":
            from app.motion_designer.advanced_presets import apply_advanced_preset

            candidate = MotionComposition.from_dict(self.controller.composition.to_dict())
            layer_ids = [self._selected_layer_id] if self._selected_layer_id else []
            result = apply_advanced_preset(
                candidate,
                kind,
                layer_ids=layer_ids,
                start_ms=self._time_ms,
            )
            self.controller.replace(candidate)
            added = list(result.get("added_layer_ids") or [])
            if added:
                self._select_layer(added[-1])

    def _update_media_panel(self, composition: MotionComposition) -> None:
        self.media.clear()
        seen: set[str] = set()
        for layer in reversed(composition.layers):
            uri = str(layer.source.uri or "")
            if uri and uri not in seen:
                seen.add(uri)
                self.media.addItem(Path(uri).name)

    def _set_layer_timing(self, layer_id: str, in_ms: int, out_ms: int) -> None:
        self.controller.update_layer(layer_id, {"in_ms": int(in_ms), "out_ms": int(out_ms)})

    def _update_layer_flags(self, layer_id: str, changes: dict) -> None:
        if layer_id:
            self.controller.update_layer(layer_id, changes)

    def _delete_selected(self) -> None:
        layer_id = self._selected_layer_id
        if not layer_id:
            return
        remaining = [item.id for item in self.controller.composition.layers if item.id != layer_id]
        self._selected_layer_id = ""
        self.controller.delete_layer(layer_id)
        self._select_layer(remaining[-1] if remaining else "")

    def _duplicate_selected(self) -> None:
        if self._selected_layer_id:
            self._select_layer(self.controller.duplicate_layer(self._selected_layer_id))

    def _move_layer(self, layer_id: str, dx: float, dy: float) -> None:
        layer = find_layer(self.controller.composition, layer_id)
        position = list(layer.transform.position.default)
        self.controller.update_layer(layer_id, {"transform": {
            **layer.transform.to_dict(), "position": {**layer.transform.position.to_dict(),
            "default": [float(position[0]) + dx, float(position[1]) + dy]}}})

    def _move_rig_bone(
        self,
        rig_id: str,
        bone_id: str,
        x: float,
        y: float,
    ) -> None:
        self.controller.update_rig_bone(
            rig_id,
            bone_id,
            {"rest_position": [float(x), float(y)]},
        )

    def _select_rig_bone(self, rig_id: str, bone_id: str) -> None:
        self.rig.select_bone(rig_id, bone_id)
        self.timeline.set_selected_rig_bone(rig_id, bone_id)
        self.left_tabs.setCurrentWidget(self.inspector_tabs)
        self.inspector_tabs.setCurrentWidget(self.rig)

    def _select_puppet_pin(self, layer_id: str, pin_id: str) -> None:
        self.puppet.select_pin(layer_id, pin_id)
        self.timeline.set_selected_puppet_pin(layer_id, pin_id)
        self.left_tabs.setCurrentWidget(self.inspector_tabs)
        self.inspector_tabs.setCurrentWidget(self.puppet)

    def _set_vector_path(self, layer_id: str, path_data: object) -> None:
        layer = find_layer(self.controller.composition, layer_id)
        source = layer.source.to_dict()
        source["params"] = {**source.get("params", {}), "shape": "path", "path": path_data}
        self.controller.update_layer(layer_id, {"source": source})

    def _set_typography_path(self, layer_id: str, path_data: object) -> None:
        layer = find_layer(self.controller.composition, layer_id)
        if layer.layer_type != "text":
            return
        source = layer.source.to_dict()
        source["params"] = {**source.get("params", {}), "text_path": path_data}
        self.controller.update_layer(layer_id, {"source": source})

    def _set_typography_path_offset(self, layer_id: str, value: float) -> None:
        layer = find_layer(self.controller.composition, layer_id)
        if layer.layer_type != "text":
            return
        source = layer.source.to_dict()
        params = dict(source.get("params", {}))
        current = deepcopy(params.get("text_path_offset"))
        if isinstance(current, dict) and ("default" in current or "keyframes" in current):
            current["default"] = float(value)
            params["text_path_offset"] = current
        else:
            params["text_path_offset"] = float(value)
        source["params"] = params
        self.controller.update_layer(layer_id, {"source": source})

    def _set_source_params(self, changes: object, expected_layer_type: str) -> None:
        if not self._selected_layer_id or not isinstance(changes, dict):
            return
        layer = find_layer(self.controller.composition, self._selected_layer_id)
        if layer.layer_type != expected_layer_type:
            return
        source = layer.source.to_dict()
        source["params"] = {**source.get("params", {}), **changes}
        self.controller.update_layer(layer.id, {"source": source})

    def _set_vector_params(self, changes: object) -> None:
        self._set_source_params(changes, "shape")

    def _set_typography_params(self, changes: object) -> None:
        self._set_source_params(changes, "text")

    def _set_image_params(self, changes: object) -> None:
        if not self._selected_layer_id or not isinstance(changes, dict):
            return
        layer = find_layer(self.controller.composition, self._selected_layer_id)
        if layer.layer_type != "image":
            return
        source = layer.source.to_dict()
        params = dict(source.get("params", {}))
        for name, value in changes.items():
            current = deepcopy(params.get(name))
            if isinstance(current, dict) and (
                "default" in current or "keyframes" in current
            ):
                current["default"] = float(value)
                params[name] = current
            else:
                params[name] = value
        source["params"] = params
        self.controller.update_layer(layer.id, {"source": source})

    def _set_image_keyframe(self, parameter_name: str) -> None:
        if not self._selected_layer_id:
            return
        layer = find_layer(self.controller.composition, self._selected_layer_id)
        if layer.layer_type != "image":
            return
        self.controller.set_source_keyframe(
            layer.id,
            str(parameter_name),
            self.image.value(parameter_name),
            max(0, self._time_ms - layer.in_ms),
        )

    def _plan_ai_request(self, payload: object) -> None:
        if self._ai_generation_job is not None:
            return
        values = payload if isinstance(payload, dict) else {}
        segmentation_mode = str(values.get("segmentation_mode") or "auto")
        if (
            bool(values.get("decompose_images", True))
            and segmentation_mode in {"auto", "birefnet", "sam2"}
            and not bool(values.get("segmentation_setup_ready"))
        ):
            self.ai.set_error(
                "AI-quality cutout is not installed. Use Install cutout AI, "
                "or explicitly choose Legacy Basic."
            )
            return
        from app.ai_providers import effective_generation_provider_id
        requested_provider = str(values.get("provider") or "").strip()
        effective_provider = (
            "rule_based"
            if requested_provider in {"local_layout", "rule_based"}
            else effective_generation_provider_id()
        )
        if effective_provider == "rule_based" and not bool(
            values.get("decompose_images", True)
        ):
            from app.motion_designer.ai_generation import generate_motion_ai_proposal

            try:
                proposal = generate_motion_ai_proposal(
                    self.controller.composition,
                    str(values.get("prompt") or ""),
                    values.get("references") or [],
                    provider_id="rule_based",
                    decompose_images=bool(values.get("decompose_images", True)),
                    max_decomposed_elements=int(
                        values.get("max_decomposed_elements", 5)
                    ),
                    segmentation_mode=str(
                        values.get("segmentation_mode") or "auto"
                    ),
                    inpaint_mode=str(values.get("inpaint_mode") or "auto"),
                    reconstruct_text=bool(
                        values.get("reconstruct_text", True)
                    ),
                    ocr_native_threshold=float(
                        values.get("ocr_native_threshold", 0.78)
                    ),
                    motion_variant=str(
                        values.get("motion_variant") or "auto"
                    ),
                )
            except Exception as exc:
                self.ai.set_error(str(exc))
            else:
                self.ai.set_proposal(proposal.to_dict())
            return
        thread = QThread(self)
        worker = MotionAIGenerationWorker(self.controller.composition, values)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.completed.connect(self._finish_ai_generation)
        worker.failed.connect(self._fail_ai_generation)
        worker.completed.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(lambda: self._clear_ai_generation_job(thread))
        self._ai_generation_job = (thread, worker)
        self.ai.set_generating(True)
        thread.start()

    def _finish_ai_generation(self, proposal: object) -> None:
        self.ai.set_generating(False)
        if isinstance(proposal, dict):
            if proposal.get("schema") == "tigerstudio.motion.ai.candidate_set.v1":
                self.ai.set_candidate_set(proposal)
                self._start_ai_candidate_previews(proposal)
            else:
                self.ai.set_proposal(proposal)
        else:
            self.ai.set_error("Motion AI returned an invalid proposal.")

    def _fail_ai_generation(self, message: str) -> None:
        self.ai.set_error(message)

    def _clear_ai_generation_job(self, thread: QThread) -> None:
        if self._ai_generation_job is not None and self._ai_generation_job[0] is thread:
            self._ai_generation_job = None

    def _start_ai_candidate_previews(self, payload: dict) -> None:
        candidates = [
            dict(item)
            for item in payload.get("candidates", [])
            if isinstance(item, dict)
        ]
        if len(candidates) < 2:
            return
        if self._ai_preview_job is not None:
            self._ai_preview_pending = dict(payload)
            self._ai_preview_job[1].cancel()
            return
        from PySide6.QtCore import QStandardPaths

        cache_base = QStandardPaths.writableLocation(QStandardPaths.CacheLocation)
        cache_root = Path(cache_base or Path.home() / ".tigercapture") / "motion_ai" / "candidate_previews"
        thread = QThread(self)
        worker = MotionAICandidatePreviewWorker(
            self.controller.composition,
            candidates,
            cache_root,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.completed.connect(self.ai.set_candidate_previews)
        worker.failed.connect(self.ai.set_candidate_preview_error)
        worker.completed.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(lambda: self._clear_ai_preview_job(thread))
        self._ai_preview_job = (thread, worker)
        thread.start()

    def _clear_ai_preview_job(self, thread: QThread) -> None:
        if self._ai_preview_job is not None and self._ai_preview_job[0] is thread:
            self._ai_preview_job = None
            pending = self._ai_preview_pending
            self._ai_preview_pending = None
            if pending is not None:
                QTimer.singleShot(
                    0,
                    lambda payload=dict(pending): self._start_ai_candidate_previews(payload),
                )

    def _plan_ai_patch(self, payload: object) -> None:
        if self._ai_patch_job is not None or not isinstance(payload, dict):
            return
        thread = QThread(self)
        worker = MotionAIPatchWorker(
            self.controller.composition,
            str(payload.get("prompt") or ""),
            [str(item) for item in payload.get("layer_ids", [])],
            str(payload.get("provider") or ""),
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.completed.connect(self._finish_ai_patch)
        worker.failed.connect(self._fail_ai_patch)
        worker.completed.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(lambda: self._clear_ai_patch_job(thread))
        self._ai_patch_job = (thread, worker)
        self.ai.set_patch_planning(True)
        thread.start()

    def _finish_ai_patch(self, payload: object) -> None:
        self.ai.set_patch_planning(False)
        if isinstance(payload, dict):
            self.ai.set_patch(payload)
        else:
            self.ai.set_error("Motion AI returned an invalid revision.")

    def _fail_ai_patch(self, message: str) -> None:
        self.ai.set_patch_planning(False)
        self.ai.set_error(message)

    def _clear_ai_patch_job(self, thread: QThread) -> None:
        if self._ai_patch_job is not None and self._ai_patch_job[0] is thread:
            self._ai_patch_job = None

    def _repair_ai_decomposition(self, payload: object) -> None:
        if not isinstance(payload, dict) or not isinstance(self.ai._proposal, dict):
            return
        from app.motion_designer.ai_planner import analyze_motion_ai_layers
        from app.motion_designer.image_decomposition import (
            ImageDecompositionResult,
            compile_decomposition_layers,
        )

        proposal = deepcopy(self.ai._proposal)
        raw_layers = [
            item for item in proposal.get("layers", []) if isinstance(item, dict)
        ]
        reference_id = str(payload.get("reference_id") or "")
        beat_id = str(payload.get("beat_id") or "")

        def belongs_to_decomposition(item: dict) -> bool:
            metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
            decomposition = (
                metadata.get("image_decomposition")
                if isinstance(metadata.get("image_decomposition"), dict)
                else {}
            )
            return (
                (not reference_id or decomposition.get("reference_id") == reference_id)
                and (not beat_id or metadata.get("ai_beat_id") == beat_id)
                and bool(decomposition)
            )

        indexes = [
            index for index, item in enumerate(raw_layers)
            if belongs_to_decomposition(item)
        ]
        if not indexes:
            self.ai.set_error("The repaired decomposition no longer matches this candidate.")
            return
        old_layers = [MotionLayer.from_dict(raw_layers[index]) for index in indexes]
        background = next(
            (
                item for item in old_layers
                if item.metadata.get("image_decomposition", {}).get("role")
                == "background"
            ),
            old_layers[0],
        )
        generation = (
            proposal.get("analysis", {}).get("generation_plan", {})
            if isinstance(proposal.get("analysis"), dict)
            else {}
        )
        beat = next(
            (
                item for item in generation.get("beats", [])
                if isinstance(item, dict) and str(item.get("id") or "") == beat_id
            ),
            {},
        )
        source_width = int(background.source.params.get("width", self.controller.composition.width))
        source_height = int(background.source.params.get("height", self.controller.composition.height))
        center = background.transform.position.default
        compiled = compile_decomposition_layers(
            self.controller.composition,
            ImageDecompositionResult.from_dict(payload),
            reference_id=reference_id or "layered_image",
            name=background.name.removesuffix(" / Background"),
            in_ms=background.in_ms,
            out_ms=background.out_ms,
            center=(float(center[0]), float(center[1])),
            size=(source_width, source_height),
            beat_id=beat_id,
            motion_style=str(beat.get("motion") or "pop"),
            motion_variant=str(
                proposal.get("analysis", {}).get("motion_variant") or "auto"
            ),
            prompt=str(generation.get("prompt") or ""),
        )
        generation_id = str(old_layers[0].metadata.get("ai_generation_id") or "")
        for layer in compiled:
            if generation_id:
                layer.metadata["ai_generation_id"] = generation_id
        first_index = min(indexes)
        kept = [
            item for index, item in enumerate(raw_layers) if index not in indexes
        ]
        for offset, layer in enumerate(compiled):
            kept.insert(first_index + offset, layer.to_dict())
        proposal["layers"] = kept

        old_analysis = (
            proposal.get("analysis") if isinstance(proposal.get("analysis"), dict) else {}
        )
        rebuilt = analyze_motion_ai_layers(
            self.controller.composition,
            [MotionLayer.from_dict(item) for item in kept],
        )
        for key in (
            "generation_plan",
            "provider_contract",
            "motion_variant",
        ):
            if key in old_analysis:
                rebuilt[key] = deepcopy(old_analysis[key])
        reports = [
            dict(item)
            for item in old_analysis.get("image_decompositions", [])
            if isinstance(item, dict)
        ]
        replacement_index = next(
            (
                index for index, item in enumerate(reports)
                if (
                    (not reference_id or item.get("reference_id") == reference_id)
                    and (not beat_id or item.get("beat_id") == beat_id)
                )
            ),
            -1,
        )
        if replacement_index >= 0:
            reports[replacement_index] = dict(payload)
        else:
            reports.append(dict(payload))
        rebuilt["image_decompositions"] = reports
        rebuilt["decomposed_reference_count"] = len({
            str(item.get("reference_id") or "") for item in reports
        })
        proposal["analysis"] = rebuilt
        proposal["warnings"] = list(dict.fromkeys([
            *[str(item) for item in proposal.get("warnings", [])],
            *[str(item) for item in rebuilt.get("warnings", [])],
        ]))
        self.ai.update_current_proposal(proposal)

    def _apply_ai_proposal(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return
        candidate = apply_motion_ai_proposal(self.controller.composition, payload)
        added_ids = [item.id for item in candidate.layers[len(self.controller.composition.layers):]]
        self.controller.replace(candidate)
        if added_ids:
            self._select_layer(added_ids[-1])
        self.ai.set_applied(len(added_ids), added_ids)

    def _apply_ai_patch(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return
        from app.motion_designer.ai_generation import apply_motion_ai_patch

        operation_count = len(payload.get("operations") or [])
        candidate = apply_motion_ai_patch(self.controller.composition, payload)
        self.controller.replace(candidate)
        preview_from = max(
            0,
            min(
                (
                    find_layer(candidate, str(item.get("layer_id") or "")).in_ms
                    for item in payload.get("operations", [])
                    if isinstance(item, dict)
                ),
                default=0,
            ) - 500,
        )
        self._set_time(preview_from)
        self.timeline.set_time(preview_from)
        self.ai.set_patch_applied(operation_count)

    def _set_inspector_property(self, key: str, value: float) -> None:
        if self.inspector.is_loading() or not self._selected_layer_id:
            return
        layer = find_layer(self.controller.composition, self._selected_layer_id)
        transform = layer.transform.to_dict()
        mapping = {"x": ("position", 0), "y": ("position", 1), "scale_x": ("scale", 0),
                   "scale_y": ("scale", 1), "anchor_x": ("anchor", 0), "anchor_y": ("anchor", 1)}
        if key in mapping:
            prop_name, index = mapping[key]
            prop = dict(transform[prop_name])
            default = list(prop["default"])
            default[index] = float(value)
            prop["default"] = default
            transform[prop_name] = prop
        else:
            prop = "rotation" if key == "rotation" else "opacity"
            transform[prop] = {**transform[prop], "default": float(value)}
        self.controller.update_layer(layer.id, {"transform": transform})

    def _set_keyframe(self, key: str) -> None:
        if not self._selected_layer_id:
            return
        values = self.inspector.values()
        if key in {"x", "y"}:
            prop, value = "position", [values["x"], values["y"]]
        elif key in {"scale_x", "scale_y"}:
            prop, value = "scale", [values["scale_x"], values["scale_y"]]
        elif key in {"anchor_x", "anchor_y"}:
            prop, value = "anchor", [values["anchor_x"], values["anchor_y"]]
        else:
            prop, value = key, values[key]
        self.controller.set_keyframe(self._selected_layer_id, prop, value, self._time_ms)

    def _add_behavior(self, kind: str) -> None:
        if not self._selected_layer_id:
            return
        layer = find_layer(self.controller.composition, self._selected_layer_id)
        span = max(1, layer.out_ms - layer.in_ms)
        defaults = {
            "fade": {"direction": "in"}, "slide": {"direction": "in", "distance": [180.0, 0.0]},
            "pop": {"from": .8, "overshoot": .12},
            "spring": {"amplitude": 20.0, "frequency": 3.0, "damping": 5.0},
            "wiggle": {"amplitude": 5.0, "frequency": 2.0},
        }
        behavior = MotionBehaviorRef(kind=kind, start_ms=0, end_ms=min(span, 700),
                                     params=dict(defaults.get(kind, {})))
        self.controller.update_layer(layer.id, {
            "behaviors": [*[item.to_dict() for item in layer.behaviors], behavior.to_dict()]
        })

    def _delete_behavior(self, behavior_id: str) -> None:
        if not self._selected_layer_id:
            return
        layer = find_layer(self.controller.composition, self._selected_layer_id)
        self.controller.update_layer(layer.id, {
            "behaviors": [item.to_dict() for item in layer.behaviors if item.id != behavior_id]
        })

    def _set_behavior_param(self, behavior_id: str, key: str, value: float) -> None:
        if not self._selected_layer_id:
            return
        layer = find_layer(self.controller.composition, self._selected_layer_id)
        rows = [item.to_dict() for item in layer.behaviors]
        for item in rows:
            if item["id"] != behavior_id:
                continue
            if key in {"start_ms", "end_ms"}:
                item[key] = int(round(value))
            elif key in {"distance_x", "distance_y"}:
                distance = list(item.setdefault("params", {}).get("distance") or [100.0, 0.0])
                distance[0 if key == "distance_x" else 1] = float(value)
                item["params"]["distance"] = distance
            else:
                item.setdefault("params", {})[key] = float(value)
        self.controller.update_layer(layer.id, {"behaviors": rows})

    def _add_effect(self, kind: str) -> None:
        if not self._selected_layer_id:
            return
        layer = find_layer(self.controller.composition, self._selected_layer_id)
        if kind == "craft_style":
            from app.motion_designer.craft_style import make_craft_style_effect

            effect = make_craft_style_effect()
            self.controller.update_layer(layer.id, {
                "effects": [*[item.to_dict() for item in layer.effects], effect.to_dict()]
            })
            return
        defaults = {
            "brightness_contrast": {"brightness": 0.0, "contrast": 1.0},
            "saturation": {"amount": 1.0}, "gaussian_blur": {"radius": 4.0},
            "glow": {"threshold": .7, "radius": 8.0, "intensity": .7},
            "unsharp_mask": {"radius": 2.0, "amount": .75},
            "vignette": {"amount": .35, "softness": .65},
            "drop_shadow": {
                "offset_x": 12.0, "offset_y": 12.0, "radius": 10.0,
                "opacity": .65, "color": "#000000",
            },
            "light_sweep": {
                "center_x": .5, "center_y": .5, "angle": -24.0,
                "width": .16, "softness": .45, "intensity": 1.2,
                "color": "#ffffff",
            },
            "fractal_noise": {
                "amount": .35, "scale": 120.0, "octaves": 4.0,
                "contrast": 1.4, "evolution": 0.0, "speed": 0.0, "seed": 1.0,
            },
            "posterize": {"levels": 8.0, "amount": 1.0},
        }
        effect = MotionEffectRef(kind=kind, params={
            key: AnimatedProperty(default=value) for key, value in defaults.get(kind, {}).items()
        })
        self.controller.update_layer(layer.id, {"effects": [*[item.to_dict() for item in layer.effects], effect.to_dict()]})

    def _apply_craft_style(self, preset: str, settings: object) -> None:
        if not self._selected_layer_id:
            return
        from app.motion_designer.craft_style import (
            is_craft_style_effect,
            make_craft_style_effect,
        )

        layer = find_layer(self.controller.composition, self._selected_layer_id)
        previous = next(
            (item for item in layer.effects if is_craft_style_effect(item)),
            None,
        )
        values = settings if isinstance(settings, dict) else {}
        effect = make_craft_style_effect(values, preset=preset)
        rows = [item.to_dict() for item in layer.effects]
        if previous is None:
            rows.append(effect.to_dict())
        else:
            effect.id = previous.id
            if "texture" in previous.metadata:
                effect.metadata["texture"] = dict(previous.metadata["texture"])
            rows[layer.effects.index(previous)] = effect.to_dict()
        self.controller.update_layer(layer.id, {"effects": rows})

    def _clear_craft_style(self) -> None:
        if not self._selected_layer_id:
            return
        from app.motion_designer.craft_style import is_craft_style_effect

        layer = find_layer(self.controller.composition, self._selected_layer_id)
        self.controller.update_layer(layer.id, {
            "effects": [
                item.to_dict()
                for item in layer.effects
                if not is_craft_style_effect(item)
            ],
        })

    def _attach_craft_texture(self, uri: str) -> None:
        if not self._selected_layer_id:
            return
        from pathlib import Path
        from app.motion_designer.craft_style import (
            is_craft_style_effect,
            make_craft_style_effect,
        )

        path = Path(uri).resolve()
        if "debugcapture" in {part.lower() for part in path.parts} or not path.is_file():
            return
        layer = find_layer(self.controller.composition, self._selected_layer_id)
        effect = next(
            (item for item in layer.effects if is_craft_style_effect(item)),
            None,
        )
        rows = [item.to_dict() for item in layer.effects]
        if effect is None:
            effect = make_craft_style_effect()
            rows.append(effect.to_dict())
            effect_index = len(rows) - 1
        else:
            effect_index = layer.effects.index(effect)
        effect.metadata["texture"] = {
            "uri": str(path),
            "blend_mode": "multiply",
            "opacity": 0.25,
            "revision": str(path.stat().st_mtime_ns),
        }
        rows[effect_index] = effect.to_dict()
        self.controller.update_layer(layer.id, {"effects": rows})

    def _set_adjustment_scope(self, mode: str, layer_ids: object) -> None:
        if not self._selected_layer_id:
            return
        values = (
            [str(item) for item in layer_ids]
            if isinstance(layer_ids, (list, tuple))
            else []
        )
        self.controller.set_adjustment_scope(
            self._selected_layer_id,
            str(mode),
            values,
        )

    def _set_effect_group_scope(self, mode: str, layer_ids: object) -> None:
        if not self._selected_layer_id:
            return
        values = (
            [str(item) for item in layer_ids]
            if isinstance(layer_ids, (list, tuple))
            else []
        )
        self.controller.set_effect_group_scope(
            self._selected_layer_id,
            str(mode),
            values,
        )

    def _delete_effect(self, effect_id: str) -> None:
        layer = find_layer(self.controller.composition, self._selected_layer_id)
        self.controller.update_layer(layer.id, {"effects": [item.to_dict() for item in layer.effects if item.id != effect_id]})

    def _set_effect_param(self, effect_id: str, key: str, value: float) -> None:
        layer = find_layer(self.controller.composition, self._selected_layer_id)
        effect = next((item for item in layer.effects if item.id == effect_id), None)
        if effect is None:
            return
        prop = effect.params.get(key)
        self.controller.set_effect_parameter(
            layer.id,
            effect_id,
            key,
            value,
            time_ms=self._layer_local_time(layer) if prop is not None and prop.keyframes else None,
        )

    def _toggle_effect_keyframe(
        self,
        effect_id: str,
        key: str,
        value,
        add: bool,
    ) -> None:
        layer = find_layer(self.controller.composition, self._selected_layer_id)
        local_time = self._layer_local_time(layer)
        if add:
            self.controller.set_effect_parameter(
                layer.id, effect_id, key, value, time_ms=local_time,
            )
        else:
            self.controller.remove_effect_keyframe(
                layer.id, effect_id, key, local_time,
            )

    def _add_mask(self, kind: str) -> None:
        if not self._selected_layer_id:
            return
        layer = find_layer(self.controller.composition, self._selected_layer_id)
        width = float(layer.source.params.get("width", 400))
        height = float(layer.source.params.get("height", 220))
        params = {
            "x": AnimatedProperty(default=0.0), "y": AnimatedProperty(default=0.0),
            "width": AnimatedProperty(default=width), "height": AnimatedProperty(default=height),
            "radius": AnimatedProperty(default=0.0),
            "feather": AnimatedProperty(default=0.0),
            "expansion": AnimatedProperty(default=0.0),
            "opacity": AnimatedProperty(default=1.0),
        }
        if kind == "path":
            path = default_pen_path(width, height)
            path.closed = True
            params["path"] = AnimatedProperty(value_type="path", default=path.to_dict())
        mask = MotionMaskRef(kind=kind, mode="add", params=params)
        self.controller.update_layer(layer.id, {"masks": [*[item.to_dict() for item in layer.masks], mask.to_dict()]})

    def _delete_mask(self, mask_id: str) -> None:
        layer = find_layer(self.controller.composition, self._selected_layer_id)
        self.controller.update_layer(layer.id, {"masks": [item.to_dict() for item in layer.masks if item.id != mask_id]})

    def _set_mask_param(self, mask_id: str, key: str, value: float) -> None:
        layer = find_layer(self.controller.composition, self._selected_layer_id)
        mask = next((item for item in layer.masks if item.id == mask_id), None)
        if mask is None:
            return
        prop = mask.params.get(key)
        self.controller.set_mask_parameter(
            layer.id,
            mask_id,
            key,
            value,
            time_ms=self._layer_local_time(layer) if prop is not None and prop.keyframes else None,
        )

    def _toggle_mask_keyframe(
        self,
        mask_id: str,
        key: str,
        value,
        add: bool,
    ) -> None:
        layer = find_layer(self.controller.composition, self._selected_layer_id)
        local_time = self._layer_local_time(layer)
        if add:
            self.controller.set_mask_parameter(
                layer.id, mask_id, key, value, time_ms=local_time,
            )
        else:
            self.controller.remove_mask_keyframe(
                layer.id, mask_id, key, local_time,
            )

    def _set_mask_item(self, mask_id: str, key: str, value: object) -> None:
        layer = find_layer(self.controller.composition, self._selected_layer_id)
        masks = [item.to_dict() for item in layer.masks]
        for item in masks:
            if item["id"] != mask_id:
                continue
            if key == "mode":
                item["mode"] = str(value)
            elif key == "tracking_mode":
                metadata = item.setdefault("metadata", {})
                if value == "none":
                    metadata.pop("tracking_cache", None)
                else:
                    tracking = dict(metadata.get("tracking_cache") or {})
                    tracking.update({"enabled": True, "mode": str(value)})
                    tracking.setdefault("origin", [0.0, 0.0])
                    tracking.setdefault("samples", [])
                    metadata["tracking_cache"] = tracking
            elif key == "tracking_frozen":
                metadata = item.setdefault("metadata", {})
                tracking = dict(metadata.get("tracking_cache") or {})
                if value and not tracking.get("samples"):
                    continue
                tracking["frozen"] = bool(value)
                metadata["tracking_cache"] = tracking
        self.controller.update_layer(layer.id, {"masks": masks})

    def _apply_composition_track(self, track_id: str, stabilize: bool) -> None:
        if not self._selected_layer_id:
            return
        from app.motion_designer.tracking_workflow import apply_track_to_layer

        composition = self.controller.composition
        asset = next(
            (
                item
                for item in composition.metadata.get("tracking_assets", [])
                if isinstance(item, dict)
                and str(item.get("id") or "") == str(track_id)
            ),
            None,
        )
        if asset is None:
            return
        source = find_layer(composition, self._selected_layer_id)
        candidate = MotionLayer.from_dict(source.to_dict())
        apply_track_to_layer(candidate, asset, stabilize=bool(stabilize))
        self.controller.update_layer(
            source.id,
            {"transform": candidate.transform.to_dict()},
        )

    def _start_composition_tracking(self, mode: str) -> None:
        if self._composition_tracking_job is not None or not self._selected_layer_id:
            return
        from app.motion_designer.tracking_provider import MotionTrackingRequest

        composition = self.controller.composition
        layer = find_layer(composition, self._selected_layer_id)
        source_path = str(layer.source.uri or "")
        if not source_path:
            self.tracking.set_analysis_status("Selected layer has no video source.")
            return
        tracking_mode = str(mode or "point")
        job_id = f"composition:{layer.id}"
        thread = QThread(self)
        if tracking_mode == "face":
            worker = MotionFaceTrackingWorker(job_id, source_path)
        else:
            request = MotionTrackingRequest(
                video_path=source_path,
                mode=tracking_mode,
                start_ms=max(0, int(layer.source_in_ms)),
                end_ms=max(
                    int(layer.source_in_ms) + 1,
                    int(layer.source_in_ms + (layer.out_ms - layer.in_ms) * layer.time_scale),
                ),
                timeline_start_ms=int(layer.in_ms),
                timeline_time_scale=float(layer.time_scale),
                target_size=(int(composition.width), int(composition.height)),
            )
            worker = MotionTrackingWorker(job_id, request)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._progress_composition_tracking)
        worker.completed.connect(self._finish_composition_tracking)
        worker.failed.connect(self._fail_composition_tracking)
        worker.completed.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_composition_tracking_job)
        self._composition_tracking_job = (
            thread,
            worker,
            tracking_mode,
            layer.id,
        )
        self.tracking.set_analysis_status("Analyzing video... 0%", busy=True)
        thread.start()

    def _progress_composition_tracking(
        self,
        _job_id: str,
        done: int,
        total: int,
    ) -> None:
        percent = int(round(done * 100.0 / max(1, total)))
        self.tracking.set_analysis_status(
            f"Analyzing video... {percent}%",
            busy=True,
        )

    def _finish_composition_tracking(self, _job_id: str, cache: object) -> None:
        if self._composition_tracking_job is None or not isinstance(cache, dict):
            return
        from app.motion_designer.tracking_workflow import normalize_track_asset

        _thread, _worker, mode, layer_id = self._composition_tracking_job
        samples = list(cache.get("samples", []))
        if mode == "face":
            from app.motion_designer.tracking_workflow import (
                retime_tracking_samples,
            )

            layer = next(
                (
                    item
                    for item in self.controller.composition.layers
                    if item.id == layer_id
                ),
                None,
            )
            if layer is None:
                self.tracking.set_analysis_status("Tracked layer no longer exists.")
                return
            samples = retime_tracking_samples(
                samples,
                source_in_ms=int(layer.source_in_ms),
                timeline_in_ms=int(layer.in_ms),
                timeline_out_ms=int(layer.out_ms),
                time_scale=float(layer.time_scale),
            )
            if not samples:
                self.tracking.set_analysis_status(
                    "No face samples fall inside the selected layer range."
                )
                return
        asset = normalize_track_asset({
            "kind": mode,
            "name": f"{mode.title()} Track",
            "source_uri": str(cache.get("metadata", {}).get("source_uri") or ""),
            "source_revision": str(cache.get("source_revision") or ""),
            "origin": cache.get("origin", [0.0, 0.0]),
            "samples": samples,
            "metadata": cache.get("metadata", {}),
        })
        assets = [
            dict(item)
            for item in self.controller.composition.metadata.get("tracking_assets", [])
            if isinstance(item, dict)
        ]
        assets.append(asset)
        self.controller.update_composition_metadata({"tracking_assets": assets})
        count = len(asset["cache"]["samples"])
        self.tracking.set_analysis_status(f"Created {mode} track with {count} samples.")

    def _fail_composition_tracking(self, _job_id: str, message: str) -> None:
        self.tracking.set_analysis_status(str(message))

    def _clear_composition_tracking_job(self) -> None:
        self._composition_tracking_job = None
        self.tracking.set_analysis_status(self.tracking.status.text())

    def _apply_composition_track_to_corner_pin(
        self,
        track_id: str,
        effect_id: str,
    ) -> None:
        if not self._selected_layer_id:
            return
        from app.motion_designer.tracking_workflow import (
            apply_planar_track_to_corner_pin,
        )

        composition = self.controller.composition
        asset = next(
            (
                item
                for item in composition.metadata.get("tracking_assets", [])
                if isinstance(item, dict)
                and str(item.get("id") or "") == str(track_id)
            ),
            None,
        )
        if asset is None:
            return
        source = find_layer(composition, self._selected_layer_id)
        candidate = MotionLayer.from_dict(source.to_dict())
        apply_planar_track_to_corner_pin(
            candidate,
            asset,
            effect_id=effect_id,
            target_size=(
                float(source.source.params.get("width", composition.width)),
                float(source.source.params.get("height", composition.height)),
            ),
        )
        self.controller.update_layer(
            source.id,
            {"effects": [item.to_dict() for item in candidate.effects]},
        )

    def _relink_composition_track(self, track_id: str) -> None:
        from app.motion_designer.tracking_workflow import (
            normalize_track_asset,
            source_revision_for_path,
        )

        source_path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Relink Motion Track Source",
            "",
            "Video (*.mp4 *.mov *.mkv *.avi *.webm *.m4v);;All files (*)",
        )
        if not source_path:
            return
        revision = source_revision_for_path(source_path)
        if not revision:
            QMessageBox.warning(self, "Relink Motion Track", "The selected source is unreadable.")
            return
        assets = []
        changed = False
        for value in self.controller.composition.metadata.get("tracking_assets", []):
            if not isinstance(value, dict):
                continue
            item = dict(value)
            if str(item.get("id") or "") == str(track_id):
                item["source_uri"] = source_path
                item["source_revision"] = revision
                metadata = dict(item.get("metadata") or {})
                metadata["relinked"] = True
                item["metadata"] = metadata
                item = normalize_track_asset(item)
                changed = True
            assets.append(item)
        if changed:
            self.controller.update_composition_metadata({
                "tracking_assets": assets,
            })

    def _start_mask_tracking(self, mask_id: str, payload: object) -> None:
        if mask_id in self._tracking_jobs or not self._selected_layer_id:
            return
        values = payload if isinstance(payload, dict) else {}
        layer = find_layer(self.controller.composition, self._selected_layer_id)
        mask = next((item for item in layer.masks if item.id == mask_id), None)
        if mask is None:
            return
        from app.motion_designer.tracking_provider import tracking_request_for_mask

        try:
            request = tracking_request_for_mask(
                self.controller.composition,
                layer,
                mask,
                video_path=str(values.get("video_path") or ""),
                mode=str(values.get("mode") or ""),
            )
        except Exception as exc:
            self.masks.set_tracking_status(mask_id, str(exc))
            return
        thread = QThread(self)
        worker = MotionTrackingWorker(mask_id, request)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self.masks.set_tracking_progress)
        worker.completed.connect(self._finish_mask_tracking)
        worker.failed.connect(self._fail_mask_tracking)
        worker.completed.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda row_id=mask_id: self._tracking_jobs.pop(row_id, None))
        self._tracking_jobs[mask_id] = (thread, worker, layer.id)
        self.masks.set_tracking_status(mask_id, "Tracking... 0%", busy=True)
        thread.start()

    def _finish_mask_tracking(self, mask_id: str, cache: object) -> None:
        job = self._tracking_jobs.get(mask_id)
        if job is None or not isinstance(cache, dict):
            return
        _thread, _worker, layer_id = job
        layer = next((item for item in self.controller.composition.layers if item.id == layer_id), None)
        if layer is None:
            return
        masks = [item.to_dict() for item in layer.masks]
        sample_count = 0
        for item in masks:
            if item["id"] == mask_id:
                item.setdefault("metadata", {})["tracking_cache"] = dict(cache)
                sample_count = len(cache.get("samples", []))
        metadata = cache.get("metadata", {})
        suffix = " - stopped at cut" if isinstance(metadata, dict) and metadata.get("terminated_reason") == "shot_cut" else ""
        self.masks.set_tracking_status(mask_id, f"{sample_count} cached samples{suffix}")
        self.controller.update_layer(layer.id, {"masks": masks})

    def _fail_mask_tracking(self, mask_id: str, message: str) -> None:
        self.masks.set_tracking_status(mask_id, str(message), busy=False)

    def _cancel_mask_tracking(self, mask_id: str) -> None:
        job = self._tracking_jobs.get(mask_id)
        if job is not None:
            job[1].cancel()
            self.masks.set_tracking_status(mask_id, "Cancelling...", busy=True)

    def _start_audio_analysis(self, source_path: str) -> None:
        if self._audio_analysis_job is not None:
            return
        thread = QThread(self)
        worker = MotionAudioAnalysisWorker(str(source_path))
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.completed.connect(self._finish_audio_analysis)
        worker.failed.connect(self._fail_audio_analysis)
        worker.completed.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_audio_analysis_job)
        self._audio_analysis_job = (thread, worker)
        self.audio.set_busy(True, "Analyzing...")
        thread.start()

    def _clear_audio_analysis_job(self) -> None:
        self._audio_analysis_job = None

    def _finish_audio_analysis(self, cache_data: object) -> None:
        if not isinstance(cache_data, dict):
            self._fail_audio_analysis("Invalid audio analysis result")
            return
        from app.motion_designer.audio_analysis import AudioAnalysisCache

        cache = AudioAnalysisCache.from_dict(cache_data)
        candidate = MotionComposition.from_dict(self.controller.composition.to_dict())
        caches = dict(candidate.metadata.get("audio_analysis") or {})
        caches[cache.id] = cache.to_dict()
        candidate.metadata["audio_analysis"] = caches
        candidate.revision += 1
        self.controller.replace(candidate)
        self.audio.select_analysis(cache.id)
        self.audio.set_busy(False, f"{len(cache.samples)} samples / {len(cache.beat_markers)} beats")

    def _fail_audio_analysis(self, message: str) -> None:
        self.audio.set_busy(False, str(message))

    def _bind_audio_reactive(self, payload: object) -> None:
        if not self._selected_layer_id or not isinstance(payload, dict):
            return
        from app.motion_designer.audio_analysis import AudioAnalysisCache
        from app.motion_designer.audio_reactive import (
            AudioReactiveBinding, compile_binding, layer_bindings, set_layer_bindings,
        )

        candidate = MotionComposition.from_dict(self.controller.composition.to_dict())
        layer = find_layer(candidate, self._selected_layer_id)
        analysis_id = str(payload.get("analysis_id") or "")
        row = (candidate.metadata.get("audio_analysis") or {}).get(analysis_id)
        if not isinstance(row, dict):
            self.audio.set_busy(False, "Analysis not found")
            return
        binding = compile_binding(AudioReactiveBinding.from_dict(payload), AudioAnalysisCache.from_dict(row))
        bindings = layer_bindings(layer)
        bindings.append(binding)
        set_layer_bindings(layer, bindings)
        candidate.revision += 1
        self.controller.replace(candidate)
        self.audio.set_busy(False, f"Bound {binding.channel} to {binding.property_name}")

    def _bake_audio_reactive(self, sample_fps: float = 0.0) -> None:
        if not self._selected_layer_id:
            return
        from app.motion_designer.audio_reactive import bake_audio_reactive

        candidate = MotionComposition.from_dict(self.controller.composition.to_dict())
        layer = find_layer(candidate, self._selected_layer_id)
        count = bake_audio_reactive(candidate, layer, sample_fps=sample_fps or candidate.fps)
        if not count:
            self.audio.set_busy(False, "No bindings to bake")
            return
        candidate.revision += 1
        self.controller.replace(candidate)
        self.audio.set_busy(False, f"Baked {count} keyframes")

    def _set_motion_color_settings(self, settings: object) -> None:
        if not isinstance(settings, dict):
            return
        from app.motion_designer.color_management import (
            MOTION_COLOR_METADATA_KEY, MotionColorSettings, validate_motion_color_settings,
        )

        color = MotionColorSettings.from_dict(settings)
        report = validate_motion_color_settings(color)
        if not report["ok"]:
            self.output.set_busy(False, "Blocked · " + " · ".join(report["errors"]))
            return
        candidate = MotionComposition.from_dict(self.controller.composition.to_dict())
        candidate.metadata[MOTION_COLOR_METADATA_KEY] = color.to_dict()
        candidate.metadata.pop("broadcast_cache", None)
        candidate.revision += 1
        self.controller.replace(candidate)

    def _start_motion_export(self, request: object) -> None:
        if self._motion_export_job is not None or not isinstance(request, dict):
            return
        thread = QThread(self)
        worker = MotionExportWorker(self.controller.composition, request)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.completed.connect(self._finish_motion_export)
        worker.failed.connect(self._fail_motion_export)
        worker.completed.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_motion_export_job)
        self._motion_export_job = (thread, worker)
        self.output.set_busy(True, "Rendering...")
        thread.start()

    def _cancel_motion_export(self) -> None:
        if self._motion_export_job is None:
            return
        self._motion_export_job[1].cancel()
        self.output.set_busy(True, "Cancelling...")

    def _clear_motion_export_job(self) -> None:
        self._motion_export_job = None

    def _finish_motion_export(self, result: object) -> None:
        count = int(result.get("frame_count", 0)) if isinstance(result, dict) else 0
        self.output.set_busy(False, f"Export complete · {count} frame(s)")

    def _fail_motion_export(self, message: str) -> None:
        self.output.set_busy(False, str(message))

    def _start_umg_generation(
        self,
        project_path: str,
        destination_root: str,
    ) -> None:
        if self._umg_generation_job is not None:
            return
        thread = QThread(self)
        worker = MotionUMGGenerationWorker(
            self.controller.composition,
            project_path,
            destination_root,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._finish_umg_generation)
        worker.finished.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_umg_generation_job)
        self._umg_generation_job = (thread, worker)
        self.umg.set_busy(
            True,
            "Installing or updating the project plugin, then generating in Unreal...",
        )
        thread.start()

    def _finish_umg_generation(self, result: object) -> None:
        self.umg.show_result(result if isinstance(result, dict) else {})

    def _cancel_umg_generation(self) -> None:
        if self._umg_generation_job is None:
            return
        self._umg_generation_job[1].cancel()
        self.umg.set_busy(True, "Cancelling Unreal generation...")

    def _clear_umg_generation_job(self) -> None:
        self._umg_generation_job = None

    def _layer_local_time(self, layer: MotionLayer | None) -> int:
        if layer is None:
            return 0
        return max(
            0,
            int(round(remap_layer_time(layer, self._time_ms))),
        )

    def _set_time(self, time_ms: int) -> None:
        self._time_ms = int(time_ms)
        self.canvas.set_time(self._time_ms)
        self.preview.set_time(self._time_ms)
        self.timeline.tracks.set_state(self.controller.composition, self._time_ms)
        if self._selected_layer_id:
            layer = next(
                (
                    item
                    for item in self.controller.composition.layers
                    if item.id == self._selected_layer_id
                ),
                None,
            )
            self.image.set_layer(
                layer,
                max(0, self._time_ms - layer.in_ms)
                if layer is not None
                else 0,
            )
            local_time = self._layer_local_time(layer)
            self.effects.set_time(local_time)
            self.masks.set_time(local_time)

    def _set_playing(self, playing: bool) -> None:
        self._set_playback_direction(1 if playing else 0)

    def _restart_template_playback(self) -> None:
        self._set_time(0)
        self.timeline.set_time(0)
        self._playback_fractional_ms = 0.0
        if self._play_direction:
            self._play_clock.restart()
            self._play_timer.start()

    def _set_playback_direction(self, direction: int) -> None:
        direction = -1 if int(direction) < 0 else (1 if int(direction) > 0 else 0)
        duration = max(1, self.controller.composition.duration_ms)
        if direction > 0 and self._time_ms >= duration:
            self._set_time(0)
            self.timeline.set_time(0)
        elif direction < 0 and self._time_ms <= 0:
            self._set_time(duration)
            self.timeline.set_time(duration)
        self._play_direction = direction
        self._playback_fractional_ms = 0.0
        self.timeline.set_playback_direction(direction)
        if direction:
            self._play_clock.restart()
            self._play_timer.start()
        else:
            self._play_timer.stop()

    def _set_loop_playback(self, enabled: bool) -> None:
        self._loop_playback = bool(enabled)
        self.timeline.set_loop_enabled(self._loop_playback)

    def _tick(self) -> None:
        if self._play_clock.isValid():
            elapsed_ms = self._play_clock.nsecsElapsed() / 1_000_000.0
            self._play_clock.restart()
        else:
            elapsed_ms = float(self._play_timer.interval())
        self._advance_playback_elapsed(elapsed_ms)

    def _advance_playback_elapsed(self, elapsed_ms: float) -> None:
        bounded = max(0.0, min(100.0, float(elapsed_ms)))
        total = bounded + self._playback_fractional_ms
        whole_ms = int(total)
        self._playback_fractional_ms = total - whole_ms
        if whole_ms > 0:
            self._advance_playback(whole_ms)

    def _advance_playback(self, elapsed_ms: int) -> None:
        if not self._play_direction:
            return
        duration = max(1, self.controller.composition.duration_ms)
        next_time = self._time_ms + self._play_direction * max(1, int(elapsed_ms))
        if self._loop_playback:
            next_time %= duration
        elif next_time >= duration:
            next_time = duration
            self._set_playback_direction(0)
        elif next_time <= 0:
            next_time = 0
            self._set_playback_direction(0)
        self._set_time(int(next_time))
        self.timeline.set_time(int(next_time))

    def closeEvent(self, event) -> None:
        if not self._confirm_discard_document_changes():
            event.ignore()
            return
        for thread, worker, _layer_id in list(self._tracking_jobs.values()):
            worker.cancel()
            thread.quit()
        for thread, _worker, _layer_id in list(self._tracking_jobs.values()):
            thread.wait(5000)
        if self._composition_tracking_job is not None:
            thread, worker, _mode, _layer_id = self._composition_tracking_job
            worker.cancel()
            thread.quit()
            thread.wait(5000)
        if self._audio_analysis_job is not None:
            thread, worker = self._audio_analysis_job
            worker.cancel()
            thread.quit()
            thread.wait(5000)
        if self._motion_export_job is not None:
            thread, worker = self._motion_export_job
            worker.cancel()
            thread.quit()
            thread.wait(5000)
        if self._umg_generation_job is not None:
            thread, worker = self._umg_generation_job
            worker.cancel()
            thread.wait(10000)
        if self._ai_generation_job is not None:
            thread, _worker = self._ai_generation_job
            thread.quit()
            thread.wait(35000)
        if self._ai_preview_job is not None:
            self._ai_preview_pending = None
            thread, worker = self._ai_preview_job
            worker.cancel()
            thread.quit()
            thread.wait(15000)
        if self._ai_patch_job is not None:
            thread, _worker = self._ai_patch_job
            thread.quit()
            thread.wait(35000)
        super().closeEvent(event)
