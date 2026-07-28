"""Motion Designer action adapter backed by the shared composition service."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from pathlib import Path

from app.motion_designer.composition_service import CompositionService
from app.motion_designer.schema import AnimatedProperty, MotionComposition, MotionEffectRef, MotionLayer, MotionMaskRef
from app.motion_designer.validation import validate_composition
from app.motion_designer.commands import add_behavior, delete_keyframe, find_layer, set_keyframe
from app.motion_designer.evaluator import evaluate_composition
from app.motion_designer.schema import Keyframe, MotionBehaviorRef
from app.motion_designer.clip import MotionClip
from app.motion_designer.timeline_bridge import duplicate_motion_clip, split_motion_clip, composition_time_ms


class MotionAdapterMixin:
    _MOTION_IMAGE_PARAMS = {"tilt_x", "tilt_y", "perspective"}

    def _motion_clip_store(self) -> list[dict[str, Any]]:
        owner = self._require_owner()
        clips = getattr(owner, "_motion_clips", None)
        if not isinstance(clips, list):
            clips = []
            owner._motion_clips = clips
        return clips

    def _motion_sync_owner(self) -> None:
        owner = self._require_owner()
        sync = getattr(owner, "_sync_motion_state_to_player", None)
        if callable(sync):
            sync()
        rebuild = getattr(owner, "_rebuild_motion_lanes", None)
        if callable(rebuild):
            rebuild()
        refresh = getattr(getattr(owner, "_player", None), "refresh_current_frame", None)
        if callable(refresh):
            refresh()

    def _motion_store(self) -> dict[str, MotionComposition]:
        owner = self._require_owner()
        store = getattr(owner, "_motion_compositions", None)
        if not isinstance(store, dict):
            store = {}
            setattr(owner, "_motion_compositions", store)
        for key, value in list(store.items()):
            if isinstance(value, Mapping):
                store[str(key)] = MotionComposition.from_dict(value)
        return store

    def _motion_service(self) -> CompositionService:
        return CompositionService(self._motion_store().values())

    def _motion_commit(self, service: CompositionService) -> None:
        store = self._motion_store()
        store.clear()
        store.update({item.id: item for item in service.list()})

    def motion_composition_list(self) -> dict[str, Any]:
        rows = [item.to_dict() for item in self._motion_store().values()]
        return {"count": len(rows), "compositions": rows}

    def motion_ui_open(self, *, composition_id: str = "") -> dict[str, Any]:
        owner = self._require_owner()
        store = self._motion_store()
        composition = store.get(str(composition_id or ""))
        if composition is None:
            composition = MotionComposition()
            store[composition.id] = composition
        from app.motion_designer.ui import MotionDesignerWindow

        window = getattr(owner, "_motion_designer_window", None)
        if window is None:
            window = MotionDesignerWindow(composition, owner)
            window.composition_changed.connect(lambda item: self._motion_store().__setitem__(item.id, item))
            autosave = getattr(owner, "_on_motion_autosave_requested", None)
            if callable(autosave):
                window.autosave_requested.connect(autosave)
            owner._motion_designer_window = window
        window.show()
        window.raise_()
        window.activateWindow()
        return {"opened": True, "composition_id": composition.id}

    def motion_composition_create(self, **params: Any) -> dict[str, Any]:
        service = self._motion_service()
        result = service.create(**params)
        self._motion_commit(service)
        return result.to_dict()

    def motion_composition_update(self, *, composition_id: str, changes: Mapping[str, Any]) -> dict[str, Any]:
        service = self._motion_service()
        result = service.update(composition_id, changes)
        self._motion_commit(service)
        return result.to_dict()

    def motion_composition_duplicate(self, *, composition_id: str) -> dict[str, Any]:
        service = self._motion_service()
        result = service.duplicate(composition_id)
        self._motion_commit(service)
        return result.to_dict()

    def motion_composition_delete(self, *, composition_id: str) -> dict[str, Any]:
        service = self._motion_service()
        result = service.delete(composition_id)
        self._motion_commit(service)
        return result.to_dict()

    def motion_composition_validate(self, *, composition_id: str) -> dict[str, Any]:
        composition = self._motion_store().get(str(composition_id))
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        return validate_composition(composition).to_dict()

    def motion_project_save(self, *, composition_id: str, path: str) -> dict[str, Any]:
        from app.motion_designer.project_io import save_motion_project

        composition = self._motion_store().get(str(composition_id))
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        target = save_motion_project(composition, path)
        return {
            "saved": True,
            "path": str(target),
            "composition_id": composition.id,
            "revision": composition.revision,
        }

    def motion_project_load(self, *, path: str, replace_existing: bool = True) -> dict[str, Any]:
        from app.motion_designer.project_io import load_motion_project

        composition = load_motion_project(path)
        store = self._motion_store()
        if composition.id in store and not bool(replace_existing):
            raise ValueError(f"motion composition already exists: {composition.id}")
        store[composition.id] = composition
        self._motion_sync_owner()
        return {
            "loaded": True,
            "path": str(Path(path).expanduser().resolve(strict=False)),
            "composition": composition.to_dict(),
        }

    def motion_layer_list(self, *, composition_id: str) -> dict[str, Any]:
        composition = self._motion_service().get(composition_id)
        return {"composition_id": composition.id, "count": len(composition.layers),
                "layers": [layer.to_dict() for layer in composition.layers]}

    def motion_layer_add(self, *, composition_id: str, layer: Mapping[str, Any], index: int | None = None) -> dict[str, Any]:
        service = self._motion_service()
        result = service.add_layer(composition_id, MotionLayer.from_dict(layer), index=index)
        self._motion_commit(service)
        return result.to_dict()

    def motion_layer_update(self, *, composition_id: str, layer_id: str, changes: Mapping[str, Any]) -> dict[str, Any]:
        service = self._motion_service()
        result = service.update_layer(composition_id, layer_id, changes)
        self._motion_commit(service)
        return result.to_dict()

    def motion_layer_delete(self, *, composition_id: str, layer_id: str) -> dict[str, Any]:
        service = self._motion_service()
        result = service.delete_layer(composition_id, layer_id)
        self._motion_commit(service)
        return result.to_dict()

    def motion_layer_reorder(self, *, composition_id: str, layer_id: str, index: int) -> dict[str, Any]:
        service = self._motion_service()
        result = service.reorder_layer(composition_id, layer_id, index)
        self._motion_commit(service)
        return result.to_dict()

    def motion_layer_parent(self, *, composition_id: str, layer_id: str, parent_id: str = "") -> dict[str, Any]:
        service = self._motion_service()
        result = service.parent_layer(composition_id, layer_id, parent_id)
        self._motion_commit(service)
        return result.to_dict()

    def motion_button_inspect(self, *, composition_id: str, layer_id: str) -> dict[str, Any]:
        from app.motion_designer.interactive_button import button_component

        composition = self._motion_store().get(str(composition_id))
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        layer = find_layer(composition, str(layer_id))
        component = button_component(layer)
        return {
            "composition_id": composition.id,
            "layer_id": layer.id,
            "is_button": component is not None,
            "component": component.to_dict() if component is not None else None,
        }

    def motion_button_create(
        self,
        *,
        composition_id: str,
        layer_id: str,
        transition_duration_ms: int = 120,
        easing: str = "ease_out",
        hit_padding: float = 12.0,
    ) -> dict[str, Any]:
        from app.motion_designer.interactive_button import (
            button_component,
            create_button_component,
        )

        composition = self._motion_store().get(str(composition_id))
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        layer = find_layer(composition, str(layer_id))
        if button_component(layer) is not None:
            raise ValueError("layer is already a button component")
        component = create_button_component(layer, **{
            "transition_duration_ms": transition_duration_ms,
            "easing": easing,
            "hit_padding": hit_padding,
        })
        composition.revision += 1
        self._motion_sync_owner()
        return {
            "changed": True,
            "undo_label": "Create Motion Button",
            "composition_id": composition.id,
            "layer_id": layer.id,
            "component": component.to_dict(),
            "revision": composition.revision,
        }

    def motion_button_update(
        self,
        *,
        composition_id: str,
        layer_id: str,
        changes: Mapping[str, Any],
    ) -> dict[str, Any]:
        from app.motion_designer.interactive_button import (
            button_component,
            set_button_component,
            update_button_component_data,
        )

        composition = self._motion_store().get(str(composition_id))
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        layer = find_layer(composition, str(layer_id))
        component = button_component(layer)
        if component is None:
            raise ValueError("layer is not a button component")
        update_button_component_data(component, changes)
        set_button_component(layer, component)
        composition.revision += 1
        self._motion_sync_owner()
        return {
            "changed": True,
            "undo_label": "Update Motion Button",
            "composition_id": composition.id,
            "layer_id": layer.id,
            "component": component.to_dict(),
            "revision": composition.revision,
        }

    def motion_button_state_set(
        self,
        *,
        composition_id: str,
        layer_id: str,
        state: str,
    ) -> dict[str, Any]:
        return self.motion_button_update(
            composition_id=composition_id,
            layer_id=layer_id,
            changes={"active_state": state},
        )

    def motion_button_remove(self, *, composition_id: str, layer_id: str) -> dict[str, Any]:
        from app.motion_designer.interactive_button import remove_button_component

        composition = self._motion_store().get(str(composition_id))
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        layer = find_layer(composition, str(layer_id))
        if not remove_button_component(layer):
            raise ValueError("layer is not a button component")
        composition.revision += 1
        self._motion_sync_owner()
        return {
            "changed": True,
            "undo_label": "Remove Motion Button",
            "composition_id": composition.id,
            "layer_id": layer.id,
            "revision": composition.revision,
        }

    def motion_ui_binding_list(self, *, composition_id: str) -> dict[str, Any]:
        from app.motion_designer.ui_motion_binding import ui_motion_bindings

        composition = self._motion_store().get(str(composition_id))
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        bindings = [row.to_dict() for row in ui_motion_bindings(composition)]
        return {
            "composition_id": composition.id,
            "revision": composition.revision,
            "count": len(bindings),
            "bindings": bindings,
        }

    def motion_ui_binding_set(
        self,
        *,
        composition_id: str,
        binding: Mapping[str, Any],
    ) -> dict[str, Any]:
        from app.motion_designer.ui_motion_binding import (
            upsert_ui_motion_binding,
            validate_ui_motion_bindings,
        )

        composition = self._motion_store().get(str(composition_id))
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        candidate = MotionComposition.from_dict(composition.to_dict())
        updated = upsert_ui_motion_binding(candidate, binding)
        preflight = validate_ui_motion_bindings(candidate)
        if not preflight["ok"]:
            messages = "; ".join(
                str(row["message"]) for row in preflight["errors"]
            )
            raise ValueError(f"invalid UI motion binding: {messages}")
        upsert_ui_motion_binding(composition, updated.to_dict())
        composition.revision += 1
        self._motion_sync_owner()
        return {
            "changed": True,
            "undo_label": "Set UI Motion Binding",
            "composition_id": composition.id,
            "binding": updated.to_dict(),
            "preflight": validate_ui_motion_bindings(composition),
            "revision": composition.revision,
        }

    def motion_ui_binding_remove(
        self,
        *,
        composition_id: str,
        binding_id: str,
    ) -> dict[str, Any]:
        from app.motion_designer.ui_motion_binding import remove_ui_motion_binding

        composition = self._motion_store().get(str(composition_id))
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        if not remove_ui_motion_binding(composition, str(binding_id)):
            raise ValueError(f"UI motion binding not found: {binding_id}")
        composition.revision += 1
        self._motion_sync_owner()
        return {
            "changed": True,
            "undo_label": "Remove UI Motion Binding",
            "composition_id": composition.id,
            "binding_id": str(binding_id),
            "revision": composition.revision,
        }

    def motion_ui_binding_preflight(
        self,
        *,
        composition_id: str,
    ) -> dict[str, Any]:
        from app.motion_designer.ui_motion_binding import (
            validate_ui_motion_bindings,
        )

        composition = self._motion_store().get(str(composition_id))
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        return validate_ui_motion_bindings(composition)

    def motion_cut_paper_create(
        self,
        *,
        composition_id: str,
        layer_id: str,
        center_x: float,
        center_y: float,
        radius_x: float,
        radius_y: float,
        start_ms: int,
        cut_duration_ms: int = 1400,
        release_duration_ms: int = 700,
        seed: int = 17,
    ) -> dict[str, Any]:
        from app.motion_designer.cut_paper import build_cut_paper_rig

        composition = self._motion_store().get(str(composition_id))
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        source = find_layer(composition, str(layer_id))
        if source.layer_type not in {"image", "video"}:
            raise ValueError("cut paper requires an image or video source layer")
        if float(radius_x) <= 0.0 or float(radius_y) <= 0.0:
            raise ValueError("cut paper radii must be positive")
        rig = build_cut_paper_rig(
            composition,
            source,
            center_x=float(center_x),
            center_y=float(center_y),
            radius_x=float(radius_x),
            radius_y=float(radius_y),
            start_ms=int(start_ms),
            cut_duration_ms=int(cut_duration_ms),
            release_duration_ms=int(release_duration_ms),
            seed=int(seed),
        )
        insert_at = composition.layers.index(source) + 1
        composition.layers[insert_at:insert_at] = rig.layers
        composition.revision += 1
        return {
            "changed": True,
            "undo_label": "Create Cut Paper Rig",
            "composition_id": composition.id,
            "source_layer_id": source.id,
            "revision": composition.revision,
            **rig.to_dict(),
        }

    def motion_cutout_arm_wave_create(
        self,
        *,
        composition_id: str,
        torso_layer_id: str,
        upper_arm_layer_id: str,
        forearm_layer_id: str,
        hand_layer_id: str,
        shoulder: list[float],
        elbow: list[float],
        wrist: list[float],
        start_ms: int,
        end_ms: int,
        side: str = "right",
        cycles: int = 3,
    ) -> dict[str, Any]:
        from app.motion_designer.cutout_rig import ArmJointLayout, apply_arm_wave_rig

        composition = self._motion_store().get(str(composition_id))
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        points = (shoulder, elbow, wrist)
        if any(not isinstance(point, (list, tuple)) or len(point) < 2 for point in points):
            raise ValueError("shoulder, elbow, and wrist require [x, y] coordinates")
        layers = [
            find_layer(composition, layer_id)
            for layer_id in (
                torso_layer_id,
                upper_arm_layer_id,
                forearm_layer_id,
                hand_layer_id,
            )
        ]
        if len({layer.id for layer in layers}) != 4:
            raise ValueError("cutout arm rig requires four different layers")
        report = apply_arm_wave_rig(
            composition,
            torso=layers[0],
            upper_arm=layers[1],
            forearm=layers[2],
            hand=layers[3],
            joints=ArmJointLayout(
                shoulder=(float(shoulder[0]), float(shoulder[1])),
                elbow=(float(elbow[0]), float(elbow[1])),
                wrist=(float(wrist[0]), float(wrist[1])),
            ),
            start_ms=int(start_ms),
            end_ms=int(end_ms),
            side=str(side),
            cycles=int(cycles),
        )
        composition.revision += 1
        return {
            "changed": True,
            "undo_label": "Create Cutout Arm Wave",
            "composition_id": composition.id,
            "revision": composition.revision,
            **report,
        }

    def motion_keyframe_set(self, *, composition_id: str, layer_id: str, property_name: str,
                            keyframe: Mapping[str, Any]) -> dict[str, Any]:
        composition = self._motion_store().get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        set_keyframe(composition, layer_id, property_name, Keyframe.from_dict(keyframe))
        return {"changed": True, "undo_label": "Set Motion Keyframe", "revision": composition.revision}

    def motion_keyframe_add(self, **params: Any) -> dict[str, Any]:
        return self.motion_keyframe_set(**params)

    def motion_image_param_set(
        self,
        *,
        composition_id: str,
        layer_id: str,
        parameter_name: str,
        value: Any,
    ) -> dict[str, Any]:
        composition = self._motion_store().get(str(composition_id))
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        layer = find_layer(composition, layer_id)
        if layer.layer_type != "image":
            raise ValueError("motion image parameters require an image layer")
        name = str(parameter_name or "").strip()
        if name not in self._MOTION_IMAGE_PARAMS:
            raise ValueError(f"unsupported motion image parameter: {name}")
        current = layer.source.params.get(name)
        if isinstance(current, Mapping) and (
            "default" in current or "keyframes" in current
        ):
            prop = AnimatedProperty.from_dict(current)
            prop.default = float(value)
            layer.source.params[name] = prop.to_dict()
        else:
            layer.source.params[name] = float(value)
        composition.revision += 1
        self._motion_sync_owner()
        return {
            "changed": True,
            "undo_label": "Set Motion Image Parameter",
            "parameter_name": name,
            "value": float(value),
            "revision": composition.revision,
        }

    def motion_image_param_keyframe_set(
        self,
        *,
        composition_id: str,
        layer_id: str,
        parameter_name: str,
        keyframe: Mapping[str, Any],
    ) -> dict[str, Any]:
        composition = self._motion_store().get(str(composition_id))
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        layer = find_layer(composition, layer_id)
        if layer.layer_type != "image":
            raise ValueError("motion image parameters require an image layer")
        name = str(parameter_name or "").strip()
        if name not in self._MOTION_IMAGE_PARAMS:
            raise ValueError(f"unsupported motion image parameter: {name}")
        current = layer.source.params.get(name, 2.6 if name == "perspective" else 0.0)
        prop = (
            AnimatedProperty.from_dict(current)
            if isinstance(current, Mapping)
            and ("default" in current or "keyframes" in current)
            else AnimatedProperty(value_type="scalar", default=float(current))
        )
        frame = Keyframe.from_dict(keyframe)
        frame.value = float(frame.value)
        prop.keyframes = [
            item
            for item in prop.keyframes
            if item.id != frame.id and item.time_ms != frame.time_ms
        ]
        prop.keyframes.append(frame)
        prop.keyframes.sort(key=lambda item: (item.time_ms, item.id))
        layer.source.params[name] = prop.to_dict()
        composition.revision += 1
        self._motion_sync_owner()
        return {
            "changed": True,
            "undo_label": "Set Motion Image Parameter Keyframe",
            "parameter_name": name,
            "keyframe": frame.to_dict(),
            "revision": composition.revision,
        }

    def motion_image_param_keyframe_delete(
        self,
        *,
        composition_id: str,
        layer_id: str,
        parameter_name: str,
        keyframe_id: str,
    ) -> dict[str, Any]:
        composition = self._motion_store().get(str(composition_id))
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        layer = find_layer(composition, layer_id)
        name = str(parameter_name or "").strip()
        if layer.layer_type != "image" or name not in self._MOTION_IMAGE_PARAMS:
            raise ValueError("unknown motion image parameter")
        current = layer.source.params.get(name)
        if not isinstance(current, Mapping):
            raise ValueError("motion image parameter has no keyframes")
        prop = AnimatedProperty.from_dict(current)
        before = len(prop.keyframes)
        prop.keyframes = [
            item for item in prop.keyframes if item.id != str(keyframe_id)
        ]
        if len(prop.keyframes) == before:
            raise ValueError(f"motion image keyframe not found: {keyframe_id}")
        layer.source.params[name] = prop.to_dict()
        composition.revision += 1
        self._motion_sync_owner()
        return {
            "changed": True,
            "undo_label": "Delete Motion Image Parameter Keyframe",
            "parameter_name": name,
            "revision": composition.revision,
        }

    def motion_keyframe_update(self, *, composition_id: str, layer_id: str, property_name: str,
                               keyframe_id: str, changes: Mapping[str, Any]) -> dict[str, Any]:
        composition = self._motion_store().get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        prop = find_layer(composition, layer_id).transform.properties().get(property_name)
        key = next((item for item in (prop.keyframes if prop else []) if item.id == keyframe_id), None)
        if key is None:
            raise ValueError(f"motion keyframe not found: {keyframe_id}")
        data = key.to_dict()
        data.update(dict(changes))
        replacement = Keyframe.from_dict(data)
        prop.keyframes[prop.keyframes.index(key)] = replacement
        prop.keyframes.sort(key=lambda item: (item.time_ms, item.id))
        composition.revision += 1
        return {"changed": True, "undo_label": "Update Motion Keyframe", "keyframe": replacement.to_dict()}

    def motion_keyframe_copy(self, *, composition_id: str, layer_id: str, property_name: str,
                             keyframe_ids: list[str] | None = None) -> dict[str, Any]:
        composition = self._motion_store().get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        prop = find_layer(composition, layer_id).transform.properties().get(property_name)
        wanted = set(keyframe_ids or [])
        rows = [item.to_dict() for item in (prop.keyframes if prop else []) if not wanted or item.id in wanted]
        self._require_owner()._motion_keyframe_clipboard = {"value_type": prop.value_type if prop else "scalar", "keyframes": rows}
        return {"copied": len(rows), "property_name": property_name}

    def motion_keyframe_paste(self, *, composition_id: str, layer_id: str, property_name: str,
                              time_ms: int) -> dict[str, Any]:
        clipboard = getattr(self._require_owner(), "_motion_keyframe_clipboard", {}) or {}
        rows = list(clipboard.get("keyframes") or [])
        if not rows:
            raise ValueError("motion keyframe clipboard is empty")
        base = min(int(item.get("time_ms", 0) or 0) for item in rows)
        pasted = []
        for row in rows:
            data = dict(row)
            data["id"] = ""
            data["time_ms"] = int(time_ms) + int(data.get("time_ms", 0) or 0) - base
            result = self.motion_keyframe_set(composition_id=composition_id, layer_id=layer_id,
                                              property_name=property_name, keyframe=data)
            pasted.append(result)
        return {"changed": True, "undo_label": "Paste Motion Keyframes", "pasted": len(pasted)}

    def motion_keyframe_delete(self, *, composition_id: str, layer_id: str, property_name: str,
                               keyframe_id: str) -> dict[str, Any]:
        composition = self._motion_store().get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        delete_keyframe(composition, layer_id, property_name, keyframe_id)
        return {"changed": True, "undo_label": "Delete Motion Keyframe", "revision": composition.revision}

    def motion_curve_update(self, *, composition_id: str, layer_id: str, property_name: str,
                            keyframe_id: str, interpolation: str = "bezier",
                            in_tangent: list[float] | None = None, out_tangent: list[float] | None = None) -> dict[str, Any]:
        composition = self._motion_store().get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        prop = find_layer(composition, layer_id).transform.properties().get(property_name)
        key = next((item for item in (prop.keyframes if prop else []) if item.id == keyframe_id), None)
        if key is None:
            raise ValueError(f"motion keyframe not found: {keyframe_id}")
        key.interpolation = str(interpolation)
        if in_tangent is not None:
            key.in_tangent = (float(in_tangent[0]), float(in_tangent[1]))
        if out_tangent is not None:
            key.out_tangent = (float(out_tangent[0]), float(out_tangent[1]))
        composition.revision += 1
        return {"changed": True, "undo_label": "Edit Motion Curve", "keyframe": key.to_dict()}

    def motion_keyframe_set_interpolation(self, **params: Any) -> dict[str, Any]:
        return self.motion_curve_update(**params)

    def motion_curve_retime(self, *, composition_id: str, layer_id: str, property_name: str,
                            scale: float = 1.0, offset_ms: int = 0, anchor_ms: int = 0,
                            keyframe_ids: list[str] | None = None) -> dict[str, Any]:
        composition = self._motion_store().get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        prop = find_layer(composition, layer_id).transform.properties().get(property_name)
        if prop is None:
            raise ValueError(f"unknown motion property: {property_name}")
        wanted = set(keyframe_ids or [])
        count = 0
        for key in prop.keyframes:
            if not wanted or key.id in wanted:
                key.time_ms = max(0, int(round(anchor_ms + (key.time_ms - anchor_ms) * float(scale) + offset_ms)))
                count += 1
        prop.keyframes.sort(key=lambda item: (item.time_ms, item.id))
        composition.revision += 1
        return {"changed": bool(count), "undo_label": "Retime Motion Curve", "retimed": count}

    def motion_behavior_list(self, *, composition_id: str, layer_id: str) -> dict[str, Any]:
        composition = self._motion_store().get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        rows = [item.to_dict() for item in find_layer(composition, layer_id).behaviors]
        return {"count": len(rows), "behaviors": rows}

    def motion_behavior_add(self, *, composition_id: str, layer_id: str, behavior: Mapping[str, Any]) -> dict[str, Any]:
        composition = self._motion_store().get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        item = MotionBehaviorRef.from_dict(behavior)
        add_behavior(composition, layer_id, item)
        return {"changed": True, "undo_label": "Add Motion Behavior", "behavior": item.to_dict()}

    def motion_behavior_update(self, *, composition_id: str, layer_id: str, behavior_id: str,
                               changes: Mapping[str, Any]) -> dict[str, Any]:
        composition = self._motion_store().get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        layer = find_layer(composition, layer_id)
        item = next((row for row in layer.behaviors if row.id == behavior_id), None)
        if item is None:
            raise ValueError(f"motion behavior not found: {behavior_id}")
        data = item.to_dict()
        data.update(dict(changes))
        layer.behaviors[layer.behaviors.index(item)] = MotionBehaviorRef.from_dict(data)
        composition.revision += 1
        return {"changed": True, "undo_label": "Update Motion Behavior", "revision": composition.revision}

    def motion_behavior_set_param(self, *, composition_id: str, layer_id: str, behavior_id: str,
                                  key: str, value: Any) -> dict[str, Any]:
        composition = self._motion_store().get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        item = next((row for row in find_layer(composition, layer_id).behaviors if row.id == behavior_id), None)
        if item is None:
            raise ValueError(f"motion behavior not found: {behavior_id}")
        item.params[str(key)] = value
        composition.revision += 1
        return {"changed": True, "undo_label": "Set Motion Behavior Parameter", "behavior": item.to_dict()}

    def motion_behavior_bake(self, *, composition_id: str, layer_id: str, sample_fps: float = 30.0) -> dict[str, Any]:
        composition = self._motion_store().get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        layer = find_layer(composition, layer_id)
        if not layer.behaviors:
            return {"changed": False, "undo_label": "Bake Motion Behavior", "keyframes": 0}
        step = 1000.0 / max(1.0, float(sample_fps))
        samples: list[tuple[float, Any]] = []
        time_ms = float(layer.in_ms)
        while time_ms <= layer.out_ms:
            state = next(item for item in evaluate_composition(composition, time_ms) if item.id == layer_id)
            samples.append((state.local_time_ms, state))
            time_ms += step
        layer.behaviors = []
        for local_time, state in samples:
            for prop_name, value in (("position", state.position), ("scale", state.scale),
                                     ("rotation", state.rotation), ("opacity", state.opacity), ("anchor", state.anchor)):
                set_keyframe(composition, layer_id, prop_name,
                             Keyframe(time_ms=int(round(local_time)), value=value, interpolation="linear"))
        return {"changed": True, "undo_label": "Bake Motion Behavior", "keyframes": len(samples) * 5,
                "revision": composition.revision}

    def motion_behavior_delete(self, *, composition_id: str, layer_id: str, behavior_id: str) -> dict[str, Any]:
        composition = self._motion_store().get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        layer = find_layer(composition, layer_id)
        before = len(layer.behaviors)
        layer.behaviors = [item for item in layer.behaviors if item.id != behavior_id]
        if before == len(layer.behaviors):
            raise ValueError(f"motion behavior not found: {behavior_id}")
        composition.revision += 1
        return {"changed": True, "undo_label": "Delete Motion Behavior", "revision": composition.revision}

    def motion_effect_list(self, *, composition_id: str, layer_id: str) -> dict[str, Any]:
        layer = find_layer(self._motion_store()[composition_id], layer_id)
        rows = [item.to_dict() for item in layer.effects]
        return {"count": len(rows), "effects": rows}

    def motion_adjustment_scope_get(
        self,
        *,
        composition_id: str,
        layer_id: str,
    ) -> dict[str, Any]:
        from app.motion_designer.adjustment_scope import (
            adjustment_scope,
            eligible_adjustment_target_ids,
        )

        composition = self._motion_store()[composition_id]
        layer = find_layer(composition, layer_id)
        if layer.layer_type != "adjustment":
            raise ValueError("Adjustment scope requires an adjustment layer")
        return {
            "scope": adjustment_scope(layer),
            "eligible_layer_ids": eligible_adjustment_target_ids(
                composition,
                layer.id,
            ),
        }

    def motion_adjustment_scope_set(
        self,
        *,
        composition_id: str,
        layer_id: str,
        mode: str,
        layer_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        from app.motion_designer.adjustment_scope import set_adjustment_scope

        composition = self._motion_store()[composition_id]
        layer = find_layer(composition, layer_id)
        scope = set_adjustment_scope(
            composition,
            layer,
            mode=mode,
            layer_ids=layer_ids or (),
        )
        composition.revision += 1
        return {
            "changed": True,
            "undo_label": "Set Adjustment Layer Scope",
            "scope": scope,
            "revision": composition.revision,
        }

    def motion_effect_group_scope_get(
        self,
        *,
        composition_id: str,
        layer_id: str,
    ) -> dict[str, Any]:
        from app.motion_designer.effect_group import (
            descendant_layer_ids,
            effect_group_scope,
            resolved_effect_group_target_ids,
        )

        composition = self._motion_store()[composition_id]
        layer = find_layer(composition, layer_id)
        if layer.layer_type != "group":
            raise ValueError("Effect-group scope requires a group layer")
        return {
            "scope": effect_group_scope(layer),
            "eligible_layer_ids": descendant_layer_ids(composition, layer.id),
            "resolved_layer_ids": resolved_effect_group_target_ids(
                composition,
                layer,
            ),
        }

    def motion_effect_group_scope_set(
        self,
        *,
        composition_id: str,
        layer_id: str,
        mode: str,
        layer_ids: list[str] | None = None,
        enabled: bool = True,
    ) -> dict[str, Any]:
        from app.motion_designer.effect_group import set_effect_group_scope

        composition = self._motion_store()[composition_id]
        layer = find_layer(composition, layer_id)
        scope = set_effect_group_scope(
            composition,
            layer,
            enabled=enabled,
            mode=mode,
            layer_ids=layer_ids or (),
        )
        composition.revision += 1
        return {
            "changed": True,
            "undo_label": "Set Effect Group Scope",
            "scope": scope,
            "revision": composition.revision,
        }

    def motion_effect_add(self, *, composition_id: str, layer_id: str, effect: Mapping[str, Any]) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        item = MotionEffectRef.from_dict(effect)
        find_layer(composition, layer_id).effects.append(item)
        composition.revision += 1
        return {"changed": True, "undo_label": "Add Motion Effect", "effect": item.to_dict()}

    def motion_effect_update(self, *, composition_id: str, layer_id: str, effect_id: str,
                             changes: Mapping[str, Any]) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        layer = find_layer(composition, layer_id)
        item = next((row for row in layer.effects if row.id == effect_id), None)
        if item is None:
            raise ValueError(f"motion effect not found: {effect_id}")
        data = item.to_dict()
        data.update(dict(changes))
        replacement = MotionEffectRef.from_dict(data)
        layer.effects[layer.effects.index(item)] = replacement
        composition.revision += 1
        return {"changed": True, "undo_label": "Update Motion Effect", "effect": replacement.to_dict()}

    def motion_effect_delete(self, *, composition_id: str, layer_id: str, effect_id: str) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        layer = find_layer(composition, layer_id)
        before = len(layer.effects)
        layer.effects = [item for item in layer.effects if item.id != effect_id]
        if len(layer.effects) == before:
            raise ValueError(f"motion effect not found: {effect_id}")
        composition.revision += 1
        return {"changed": True, "undo_label": "Delete Motion Effect", "revision": composition.revision}

    def motion_effect_set_param(self, *, composition_id: str, layer_id: str, effect_id: str,
                                key: str, value: Any) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        item = next((row for row in find_layer(composition, layer_id).effects if row.id == effect_id), None)
        if item is None:
            raise ValueError(f"motion effect not found: {effect_id}")
        current = item.params.get(str(key))
        item.params[str(key)] = AnimatedProperty.from_dict(
            value, value_type=current.value_type if current is not None else "scalar"
        )
        composition.revision += 1
        return {"changed": True, "undo_label": "Set Motion Effect Parameter", "effect": item.to_dict()}

    def motion_effect_keyframe_set(self, *, composition_id: str, layer_id: str, effect_id: str,
                                   key: str, keyframe: Mapping[str, Any]) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        item = next((row for row in find_layer(composition, layer_id).effects if row.id == effect_id), None)
        if item is None:
            raise ValueError(f"motion effect not found: {effect_id}")
        frame = Keyframe.from_dict(keyframe)
        prop = item.params.setdefault(str(key), AnimatedProperty(default=frame.value))
        prop.keyframes = [row for row in prop.keyframes if row.id != frame.id and row.time_ms != frame.time_ms]
        prop.keyframes.append(frame)
        prop.keyframes.sort(key=lambda row: (row.time_ms, row.id))
        composition.revision += 1
        return {"changed": True, "undo_label": "Set Motion Effect Keyframe", "keyframe": frame.to_dict()}

    def motion_effect_keyframe_delete(
        self,
        *,
        composition_id: str,
        layer_id: str,
        effect_id: str,
        key: str,
        time_ms: int,
    ) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        item = next(
            (
                row for row in find_layer(composition, layer_id).effects
                if row.id == effect_id
            ),
            None,
        )
        if item is None:
            raise ValueError(f"motion effect not found: {effect_id}")
        prop = item.params.get(str(key))
        if prop is None:
            raise ValueError(f"motion effect parameter not found: {key}")
        target_time = max(0, int(time_ms))
        remaining = [
            row for row in prop.keyframes
            if int(row.time_ms) != target_time
        ]
        if len(remaining) == len(prop.keyframes):
            raise ValueError(f"motion effect keyframe not found at {target_time}ms")
        prop.keyframes = remaining
        composition.revision += 1
        return {
            "changed": True,
            "undo_label": "Delete Motion Effect Keyframe",
            "effect_id": item.id,
            "key": str(key),
            "time_ms": target_time,
        }

    def motion_mask_list(self, *, composition_id: str, layer_id: str) -> dict[str, Any]:
        layer = find_layer(self._motion_store()[composition_id], layer_id)
        rows = [item.to_dict() for item in layer.masks]
        return {"count": len(rows), "masks": rows}

    def motion_mask_add(self, *, composition_id: str, layer_id: str, mask: Mapping[str, Any]) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        item = MotionMaskRef.from_dict(mask)
        find_layer(composition, layer_id).masks.append(item)
        composition.revision += 1
        return {"changed": True, "undo_label": "Add Motion Mask", "mask": item.to_dict()}

    def motion_mask_update(self, *, composition_id: str, layer_id: str, mask_id: str,
                           changes: Mapping[str, Any]) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        layer = find_layer(composition, layer_id)
        item = next((row for row in layer.masks if row.id == mask_id), None)
        if item is None:
            raise ValueError(f"motion mask not found: {mask_id}")
        data = item.to_dict()
        data.update(dict(changes))
        replacement = MotionMaskRef.from_dict(data)
        layer.masks[layer.masks.index(item)] = replacement
        composition.revision += 1
        return {"changed": True, "undo_label": "Update Motion Mask", "mask": replacement.to_dict()}

    def motion_mask_delete(self, *, composition_id: str, layer_id: str, mask_id: str) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        layer = find_layer(composition, layer_id)
        before = len(layer.masks)
        layer.masks = [item for item in layer.masks if item.id != mask_id]
        if len(layer.masks) == before:
            raise ValueError(f"motion mask not found: {mask_id}")
        composition.revision += 1
        return {"changed": True, "undo_label": "Delete Motion Mask", "revision": composition.revision}

    def motion_mask_set_param(self, *, composition_id: str, layer_id: str, mask_id: str,
                              key: str, value: Any) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        item = next((row for row in find_layer(composition, layer_id).masks if row.id == mask_id), None)
        if item is None:
            raise ValueError(f"motion mask not found: {mask_id}")
        current = item.params.get(str(key))
        item.params[str(key)] = AnimatedProperty.from_dict(
            value, value_type=current.value_type if current is not None else "scalar"
        )
        composition.revision += 1
        return {"changed": True, "undo_label": "Set Motion Mask Parameter", "mask": item.to_dict()}

    def motion_mask_keyframe_set(self, *, composition_id: str, layer_id: str, mask_id: str,
                                 key: str, keyframe: Mapping[str, Any]) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        item = next((row for row in find_layer(composition, layer_id).masks if row.id == mask_id), None)
        if item is None:
            raise ValueError(f"motion mask not found: {mask_id}")
        frame = Keyframe.from_dict(keyframe)
        value_type = "path" if key == "path" else "scalar"
        prop = item.params.setdefault(str(key), AnimatedProperty(value_type=value_type, default=frame.value))
        prop.keyframes = [row for row in prop.keyframes if row.id != frame.id and row.time_ms != frame.time_ms]
        prop.keyframes.append(frame)
        prop.keyframes.sort(key=lambda row: (row.time_ms, row.id))
        composition.revision += 1
        return {"changed": True, "undo_label": "Set Motion Mask Keyframe", "keyframe": frame.to_dict()}

    def motion_mask_keyframe_delete(
        self,
        *,
        composition_id: str,
        layer_id: str,
        mask_id: str,
        key: str,
        time_ms: int,
    ) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        item = next(
            (
                row for row in find_layer(composition, layer_id).masks
                if row.id == mask_id
            ),
            None,
        )
        if item is None:
            raise ValueError(f"motion mask not found: {mask_id}")
        prop = item.params.get(str(key))
        if prop is None:
            raise ValueError(f"motion mask parameter not found: {key}")
        target_time = max(0, int(time_ms))
        remaining = [
            row for row in prop.keyframes
            if int(row.time_ms) != target_time
        ]
        if len(remaining) == len(prop.keyframes):
            raise ValueError(f"motion mask keyframe not found at {target_time}ms")
        prop.keyframes = remaining
        composition.revision += 1
        return {
            "changed": True,
            "undo_label": "Delete Motion Mask Keyframe",
            "mask_id": item.id,
            "key": str(key),
            "time_ms": target_time,
        }

    def motion_mask_path_set(self, *, composition_id: str, layer_id: str, mask_id: str,
                             path: Mapping[str, Any]) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        item = next((row for row in find_layer(composition, layer_id).masks if row.id == mask_id), None)
        if item is None:
            raise ValueError(f"motion mask not found: {mask_id}")
        item.kind = "path"
        item.params["path"] = AnimatedProperty(value_type="path", default=dict(path))
        composition.revision += 1
        return {"changed": True, "undo_label": "Set Motion Mask Path", "mask": item.to_dict()}

    def motion_mask_tracking_set(self, *, composition_id: str, layer_id: str, mask_id: str,
                                 tracking: Mapping[str, Any]) -> dict[str, Any]:
        from app.motion_designer.mask_adapter import TRACKING_METADATA_KEY
        from app.motion_designer.mask_tracking import MotionTrackingCache

        composition = self._motion_store()[composition_id]
        item = next((row for row in find_layer(composition, layer_id).masks if row.id == mask_id), None)
        if item is None:
            raise ValueError(f"motion mask not found: {mask_id}")
        cache = MotionTrackingCache.from_dict(tracking)
        item.metadata[TRACKING_METADATA_KEY] = cache.to_dict()
        composition.revision += 1
        return {
            "changed": True,
            "undo_label": "Set Motion Mask Tracking",
            "tracking": cache.to_dict(),
            "sample_count": len(cache.samples),
        }

    def motion_mask_tracking_generate(
        self,
        *,
        composition_id: str,
        layer_id: str,
        mask_id: str,
        video_path: str = "",
        mode: str = "",
        start_ms: int | None = None,
        end_ms: int | None = None,
        timeline_start_ms: int | None = None,
        sample_interval_ms: int = 100,
        target_size: list[int] | tuple[int, ...] | None = None,
        roi: list[float] | tuple[float, ...] | None = None,
    ) -> dict[str, Any]:
        from app.motion_designer.mask_adapter import TRACKING_METADATA_KEY
        from app.motion_designer.tracking_provider import (
            generate_tracking_cache,
            tracking_request_for_mask,
        )

        composition = self._motion_store()[composition_id]
        layer = find_layer(composition, layer_id)
        item = next((row for row in layer.masks if row.id == mask_id), None)
        if item is None:
            raise ValueError(f"motion mask not found: {mask_id}")
        from app.motion_designer.mask_tracking import MotionTrackingCache

        existing_cache = MotionTrackingCache.from_dict(
            item.metadata.get(TRACKING_METADATA_KEY),
        )
        if existing_cache.frozen:
            raise ValueError(
                "motion mask tracking cache is frozen; unfreeze it before propagation"
            )
        request = tracking_request_for_mask(
            composition,
            layer,
            item,
            video_path=video_path,
            mode=mode,
            start_ms=start_ms,
            end_ms=end_ms,
            timeline_start_ms=timeline_start_ms,
            sample_interval_ms=sample_interval_ms,
            target_size=target_size,
            roi=roi,
        )
        cache = generate_tracking_cache(request)
        item.metadata[TRACKING_METADATA_KEY] = cache.to_dict()
        composition.revision += 1
        self._motion_sync_owner()
        return {
            "changed": True,
            "undo_label": "Generate Motion Mask Tracking",
            "tracking": cache.to_dict(),
            "sample_count": len(cache.samples),
            "diagnostics": dict(cache.metadata),
        }

    def motion_mask_tracking_clear(self, *, composition_id: str, layer_id: str,
                                   mask_id: str) -> dict[str, Any]:
        from app.motion_designer.mask_adapter import TRACKING_METADATA_KEY

        composition = self._motion_store()[composition_id]
        item = next((row for row in find_layer(composition, layer_id).masks if row.id == mask_id), None)
        if item is None:
            raise ValueError(f"motion mask not found: {mask_id}")
        changed = item.metadata.pop(TRACKING_METADATA_KEY, None) is not None
        if changed:
            composition.revision += 1
        return {
            "changed": changed,
            "undo_label": "Clear Motion Mask Tracking",
            "revision": composition.revision,
        }

    def _motion_source_update(self, composition_id: str, layer_id: str,
                              changes: Mapping[str, Any], undo_label: str,
                              *, expected_layer_type: str, source_kind: str) -> dict[str, Any]:
        service = self._motion_service()
        composition = service.get(composition_id)
        layer = find_layer(composition, layer_id)
        if layer.layer_type != expected_layer_type:
            raise ValueError(f"{undo_label} requires a {expected_layer_type} layer")
        source = layer.source.to_dict()
        source["kind"] = source_kind
        source["params"] = {**source.get("params", {}), **dict(changes)}
        result = service.update_layer(composition_id, layer_id, {"source": source})
        if not result.validation.ok:
            raise ValueError(result.validation.issues[0].message)
        self._motion_commit(service)
        updated = find_layer(self._motion_store()[composition_id], layer_id)
        return {
            "changed": True, "undo_label": undo_label,
            "revision": self._motion_store()[composition_id].revision,
            "source": updated.source.to_dict(),
        }

    def _motion_vector_update(self, composition_id: str, layer_id: str,
                              changes: Mapping[str, Any], undo_label: str) -> dict[str, Any]:
        return self._motion_source_update(
            composition_id, layer_id, changes, undo_label,
            expected_layer_type="shape", source_kind="shape",
        )

    def _motion_typography_update(self, composition_id: str, layer_id: str,
                                  changes: Mapping[str, Any], undo_label: str) -> dict[str, Any]:
        return self._motion_source_update(
            composition_id, layer_id, changes, undo_label,
            expected_layer_type="text", source_kind="typography",
        )

    def motion_vector_path_set(self, *, composition_id: str, layer_id: str,
                               path: Mapping[str, Any]) -> dict[str, Any]:
        return self._motion_vector_update(
            composition_id, layer_id, {"shape": "path", "path": dict(path)}, "Set Vector Path",
        )

    def motion_vector_primitive_set(self, *, composition_id: str, layer_id: str, kind: str,
                                    params: Mapping[str, Any] | None = None) -> dict[str, Any]:
        normalized = str(kind or "rectangle").lower()
        if normalized not in {"rectangle", "ellipse", "polygon", "star", "path"}:
            raise ValueError(f"unsupported vector primitive: {kind}")
        changes = {**dict(params or {}), "shape": normalized}
        return self._motion_vector_update(composition_id, layer_id, changes, "Set Vector Primitive")

    def motion_vector_boolean_set(self, *, composition_id: str, layer_id: str,
                                  operation: str, paths: list[Mapping[str, Any]]) -> dict[str, Any]:
        normalized = str(operation or "union").lower()
        if normalized not in {"union", "subtract", "intersect", "exclude", "xor"}:
            raise ValueError(f"unsupported vector boolean operation: {operation}")
        return self._motion_vector_update(composition_id, layer_id, {
            "boolean": {"operation": normalized, "paths": [dict(path) for path in paths]},
        }, "Set Vector Boolean")

    def motion_vector_boolean_layers_set(self, *, composition_id: str, layer_id: str,
                                         operation: str, operand_layer_ids: list[str],
                                         hide_operands: bool = True) -> dict[str, Any]:
        composition = self._motion_store().get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        target = find_layer(composition, layer_id)
        if target.layer_type != "shape":
            raise ValueError("Set Vector Boolean Layers requires a shape layer")
        normalized = str(operation or "union").lower()
        if normalized not in {"union", "subtract", "intersect", "exclude", "xor"}:
            raise ValueError(f"unsupported vector boolean operation: {operation}")
        unique_ids: list[str] = []
        for value in operand_layer_ids:
            operand_id = str(value or "")
            if not operand_id or operand_id == layer_id or operand_id in unique_ids:
                continue
            operand = find_layer(composition, operand_id)
            if operand.layer_type != "shape":
                raise ValueError(f"Boolean operand must be a shape layer: {operand_id}")
            unique_ids.append(operand_id)
        current = target.source.params.get("boolean")
        current = dict(current) if isinstance(current, Mapping) else {}
        current.update({
            "operation": normalized,
            "operand_layer_ids": unique_ids,
            "hide_operands": bool(hide_operands),
        })
        return self._motion_vector_update(
            composition_id, layer_id, {"boolean": current}, "Set Vector Boolean Layers",
        )

    def motion_vector_trim_set(self, *, composition_id: str, layer_id: str,
                               start: float, end: float, offset: float = 0.0) -> dict[str, Any]:
        return self._motion_vector_update(composition_id, layer_id, {
            "trim": {"start": float(start), "end": float(end), "offset": float(offset)},
        }, "Set Vector Trim")

    def motion_vector_offset_path_set(
        self,
        *,
        composition_id: str,
        layer_id: str,
        amount: float,
        join: str = "round",
    ) -> dict[str, Any]:
        normalized_join = str(join or "round").lower()
        if normalized_join not in {"round", "miter", "bevel"}:
            raise ValueError(f"unsupported Offset Paths join: {join}")
        return self._motion_vector_update(
            composition_id,
            layer_id,
            {"offset_path": {
                "amount": float(amount),
                "join": normalized_join,
            }},
            "Set Vector Offset Paths",
        )

    def motion_vector_path_morph_set(
        self,
        *,
        composition_id: str,
        layer_id: str,
        keyframes: list[Mapping[str, Any]],
        auto_correspond: bool = True,
        target_count: int = 0,
    ) -> dict[str, Any]:
        from app.motion_designer.path_morph import set_layer_path_morph

        from app.motion_designer.schema import MotionLayer

        service = self._motion_service()
        composition = service.get(composition_id)
        source_layer = find_layer(composition, layer_id)
        layer = MotionLayer.from_dict(source_layer.to_dict())
        report = set_layer_path_morph(
            layer,
            keyframes,
            auto_correspond=auto_correspond,
            target_count=target_count,
        )
        result = service.update_layer(
            composition_id,
            layer_id,
            {
                "source": layer.source.to_dict(),
                "metadata": layer.metadata,
            },
        )
        if not result.validation.ok:
            raise ValueError(result.validation.issues[0].message)
        self._motion_commit(service)
        return {
            "changed": True,
            "undo_label": "Set Vector Path Morph",
            "revision": self._motion_store()[composition_id].revision,
            "layer_id": layer.id,
            "path_morph": report,
        }

    def motion_vector_stroke_set(
        self,
        *,
        composition_id: str,
        layer_id: str,
        color: str = "#20242b",
        width: float = 2.0,
        gradient: Mapping[str, Any] | None = None,
        dash: list[float] | None = None,
        dash_offset: float = 0.0,
        taper_start: float = 1.0,
        taper_end: float = 1.0,
        width_profile: list[float] | None = None,
    ) -> dict[str, Any]:
        if width < 0.0:
            raise ValueError("stroke width cannot be negative")
        if min(float(taper_start), float(taper_end)) < 0.0:
            raise ValueError("stroke taper cannot be negative")
        if width_profile and min(float(value) for value in width_profile) < 0.0:
            raise ValueError("stroke width profile cannot contain negative values")
        return self._motion_vector_update(
            composition_id,
            layer_id,
            {
                "stroke": str(color),
                "stroke_width": float(width),
                "stroke_gradient": dict(gradient) if gradient else None,
                "dash": [max(0.01, float(value)) for value in (dash or [])],
                "dash_offset": float(dash_offset),
                "stroke_taper": {
                    "start": float(taper_start),
                    "end": float(taper_end),
                    "profile": [float(value) for value in (width_profile or [])],
                },
            },
            "Set Vector Stroke",
        )

    def motion_vector_repeater_set(self, *, composition_id: str, layer_id: str, count: int,
                                   offset: list[float] | None = None, rotation: float = 0.0,
                                   scale: list[float] | None = None, opacity_start: float = 1.0,
                                   opacity_end: float = 1.0) -> dict[str, Any]:
        return self._motion_vector_update(composition_id, layer_id, {
            "repeater": {
                "count": int(count), "offset": list(offset or [0.0, 0.0]),
                "rotation": float(rotation), "scale": list(scale or [1.0, 1.0]),
                "opacity_start": float(opacity_start), "opacity_end": float(opacity_end),
            },
        }, "Set Vector Repeater")

    def motion_vector_param_keyframe_set(self, *, composition_id: str, layer_id: str,
                                         parameter_name: str,
                                         keyframe: Mapping[str, Any]) -> dict[str, Any]:
        composition = self._motion_store().get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        layer = find_layer(composition, layer_id)
        if layer.layer_type != "shape":
            raise ValueError("vector operations require a shape layer")
        name = str(parameter_name or "")
        current = layer.source.params.get(name)
        value_type = "path" if name == "path" else "scalar"
        frame = Keyframe.from_dict(keyframe)
        if isinstance(current, Mapping) and ("default" in current or "keyframes" in current):
            prop = AnimatedProperty.from_dict(current, value_type=value_type)
        else:
            prop = AnimatedProperty(value_type=value_type, default=current if current is not None else frame.value)
        prop.keyframes = [item for item in prop.keyframes if item.id != frame.id and item.time_ms != frame.time_ms]
        prop.keyframes.append(frame)
        prop.keyframes.sort(key=lambda item: (item.time_ms, item.id))
        return self._motion_vector_update(
            composition_id, layer_id, {name: prop.to_dict()}, "Set Vector Parameter Keyframe",
        )

    def motion_typography_style_set(self, *, composition_id: str, layer_id: str,
                                    changes: Mapping[str, Any]) -> dict[str, Any]:
        allowed = {
            "text", "font_family", "font_size", "font_weight", "font_axes",
            "italic", "underline", "fill", "stroke", "stroke_width", "alignment",
            "letter_spacing", "line_height", "width", "height", "padding",
            "shadow_color", "shadow_offset_x", "shadow_offset_y",
            "background_color", "background_radius",
        }
        unexpected = sorted(set(changes) - allowed)
        if unexpected:
            raise ValueError(f"unsupported typography style parameters: {', '.join(unexpected)}")
        return self._motion_typography_update(
            composition_id, layer_id, dict(changes), "Set Typography Style",
        )

    def motion_typography_animation_set(self, *, composition_id: str, layer_id: str,
                                        animation: Mapping[str, Any]) -> dict[str, Any]:
        return self._motion_typography_update(
            composition_id, layer_id, {"text_animation": dict(animation)},
            "Set Typography Animation",
        )

    def motion_typography_text_path_set(self, *, composition_id: str, layer_id: str,
                                        path: Mapping[str, Any], offset: float = .5) -> dict[str, Any]:
        return self._motion_typography_update(
            composition_id, layer_id,
            {"text_path": dict(path), "text_path_offset": float(offset)},
            "Set Typography Text Path",
        )

    def motion_typography_text_path_clear(self, *, composition_id: str,
                                          layer_id: str) -> dict[str, Any]:
        return self._motion_typography_update(
            composition_id, layer_id, {"text_path": None},
            "Clear Typography Text Path",
        )

    def motion_typography_text_path_offset_set(self, *, composition_id: str,
                                               layer_id: str,
                                               offset: float) -> dict[str, Any]:
        value = max(0.0, min(1.0, float(offset)))
        return self._motion_typography_update(
            composition_id, layer_id, {"text_path_offset": value},
            "Set Typography Text Path Offset",
        )

    def motion_typography_param_keyframe_set(self, *, composition_id: str, layer_id: str,
                                             parameter_name: str,
                                             keyframe: Mapping[str, Any]) -> dict[str, Any]:
        composition = self._motion_store().get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        layer = find_layer(composition, layer_id)
        if layer.layer_type != "text":
            raise ValueError("typography operations require a text layer")
        name = str(parameter_name or "")
        current = layer.source.params.get(name)
        frame = Keyframe.from_dict(keyframe)
        if isinstance(current, Mapping) and ("default" in current or "keyframes" in current):
            prop = AnimatedProperty.from_dict(current)
        else:
            prop = AnimatedProperty(default=current if current is not None else frame.value)
        prop.keyframes = [item for item in prop.keyframes if item.id != frame.id and item.time_ms != frame.time_ms]
        prop.keyframes.append(frame)
        prop.keyframes.sort(key=lambda item: (item.time_ms, item.id))
        return self._motion_typography_update(
            composition_id, layer_id, {name: prop.to_dict()},
            "Set Typography Parameter Keyframe",
        )

    def motion_typography_preflight(self, *, composition_id: str, layer_id: str) -> dict[str, Any]:
        from app.motion_designer.typography_fonts import typography_preflight

        composition = self._motion_store().get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        layer = find_layer(composition, layer_id)
        if layer.layer_type != "text":
            raise ValueError("typography preflight requires a text layer")
        return typography_preflight(layer.source.params)

    def motion_ai_plan(self, *, composition_id: str, prompt: str = "",
                       references: list[Mapping[str, Any]] | None = None,
                       provider: str = "local_layout") -> dict[str, Any]:
        from app.motion_designer.ai_workspace import build_motion_ai_proposal

        composition = self._motion_store().get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        return build_motion_ai_proposal(
            composition, prompt=prompt, references=references or [], provider=provider,
        ).to_dict()

    def motion_ai_apply(self, *, composition_id: str, proposal: Mapping[str, Any]) -> dict[str, Any]:
        from app.motion_designer.ai_workspace import apply_motion_ai_proposal

        store = self._motion_store()
        composition = store.get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        candidate = apply_motion_ai_proposal(composition, proposal)
        added = len(candidate.layers) - len(composition.layers)
        store[composition_id] = candidate
        self._motion_sync_owner()
        return {
            "changed": bool(added),
            "undo_label": "Apply Motion AI Proposal",
            "composition": candidate.to_dict(),
            "added_layers": max(0, added),
        }

    def motion_import_typography(self, *, composition_id: str, clip: Mapping[str, Any]) -> dict[str, Any]:
        from app.motion_designer.content_bridge import layer_from_typography

        service = self._motion_service()
        composition = service.get(composition_id)
        layer = layer_from_typography(clip, width=composition.width, height=composition.height)
        result = service.add_layer(composition_id, layer)
        self._motion_commit(service)
        return {"changed": True, "undo_label": "Import Typography to Motion", "layer": layer.to_dict(),
                "validation": result.validation.to_dict()}

    def motion_import_ppt_element(self, *, composition_id: str, element: Mapping[str, Any],
                                  duration_ms: int = 5000) -> dict[str, Any]:
        from app.motion_designer.content_bridge import layer_from_ppt_element

        service = self._motion_service()
        composition = service.get(composition_id)
        layer = layer_from_ppt_element(element, width=composition.width, height=composition.height,
                                       duration_ms=max(1, int(duration_ms)))
        result = service.add_layer(composition_id, layer)
        self._motion_commit(service)
        return {"changed": True, "undo_label": "Import PPT Element to Motion", "layer": layer.to_dict(),
                "validation": result.validation.to_dict()}

    def motion_export_ppt_element(self, *, composition_id: str, layer_id: str) -> dict[str, Any]:
        from app.motion_designer.content_bridge import ppt_element_from_layer

        composition = self._motion_store()[composition_id]
        element, warnings = ppt_element_from_layer(find_layer(composition, layer_id), width=composition.width,
                                                    height=composition.height)
        return {"element": element, "warnings": warnings, "native_safe": not warnings}

    def motion_clip_create_from_timeline(self, *, name: str = "Motion Composition", start_ms: int = 0,
                                         duration_ms: int = 5000) -> dict[str, Any]:
        owner = self._require_owner()
        settings = getattr(owner, "_project_settings", {}) or {}
        composition = MotionComposition(name=name, width=int(settings.get("canvas_width", 1920) or 1920),
                                        height=int(settings.get("canvas_height", 1080) or 1080),
                                        fps=float(settings.get("fps", 30.0) or 30.0), duration_ms=max(1, int(duration_ms)))
        self._motion_store()[composition.id] = composition
        clip = MotionClip(composition_id=composition.id, name=composition.name, start_ms=max(0, int(start_ms)),
                          duration_ms=composition.duration_ms)
        self._motion_clip_store().append(clip.to_dict())
        self._motion_sync_owner()
        return {"composition": composition.to_dict(), "clip": clip.to_dict(), "undo_label": "Create Motion Clip"}

    def motion_clip_place(self, *, composition_id: str, start_ms: int = 0, duration_ms: int | None = None,
                          loop: bool = False) -> dict[str, Any]:
        composition = self._motion_store().get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        clip = MotionClip(composition_id=composition.id, name=composition.name, start_ms=max(0, int(start_ms)),
                          duration_ms=max(1, int(duration_ms or composition.duration_ms)), loop=bool(loop))
        self._motion_clip_store().append(clip.to_dict())
        self._motion_sync_owner()
        return {"clip": clip.to_dict(), "undo_label": "Place Motion Clip"}

    def motion_clip_update(self, *, clip_id: str, changes: Mapping[str, Any]) -> dict[str, Any]:
        clips = self._motion_clip_store()
        index = next((i for i, item in enumerate(clips) if str(item.get("id") or "") == clip_id), -1)
        if index < 0:
            raise ValueError(f"motion clip not found: {clip_id}")
        data = dict(clips[index])
        data.update(dict(changes))
        clip = MotionClip.from_dict(data)
        clips[index] = clip.to_dict()
        self._motion_sync_owner()
        return {"clip": clip.to_dict(), "undo_label": "Update Motion Clip"}

    def motion_clip_remove(self, *, clip_id: str) -> dict[str, Any]:
        clips = self._motion_clip_store()
        before = len(clips)
        clips[:] = [item for item in clips if str(item.get("id") or "") != clip_id]
        if len(clips) == before:
            raise ValueError(f"motion clip not found: {clip_id}")
        self._motion_sync_owner()
        return {"clip_id": clip_id, "undo_label": "Remove Motion Clip"}

    def motion_clip_split(self, *, clip_id: str, timeline_ms: int) -> dict[str, Any]:
        clips = self._motion_clip_store()
        index = next((i for i, item in enumerate(clips) if str(item.get("id") or "") == clip_id), -1)
        if index < 0:
            raise ValueError(f"motion clip not found: {clip_id}")
        left, right = split_motion_clip(MotionClip.from_dict(clips[index]), int(timeline_ms))
        clips[index:index + 1] = [left.to_dict(), right.to_dict()]
        self._motion_sync_owner()
        return {"clips": [left.to_dict(), right.to_dict()], "undo_label": "Split Motion Clip"}

    def motion_clip_duplicate(self, *, clip_id: str, start_ms: int | None = None) -> dict[str, Any]:
        row = next((item for item in self._motion_clip_store() if str(item.get("id") or "") == clip_id), None)
        if row is None:
            raise ValueError(f"motion clip not found: {clip_id}")
        clip = duplicate_motion_clip(MotionClip.from_dict(row), start_ms=start_ms)
        self._motion_clip_store().append(clip.to_dict())
        self._motion_sync_owner()
        return {"clip": clip.to_dict(), "undo_label": "Duplicate Motion Clip"}

    def motion_clip_cache(self, *, clip_id: str, sample_count: int = 12) -> dict[str, Any]:
        row = next((item for item in self._motion_clip_store() if str(item.get("id") or "") == clip_id), None)
        if row is None:
            raise ValueError(f"motion clip not found: {clip_id}")
        clip = MotionClip.from_dict(row)
        composition = self._motion_store().get(clip.composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {clip.composition_id}")
        from app.motion_designer.export_renderer import MotionExportRenderer
        renderer = MotionExportRenderer(cache_capacity=max(1, int(sample_count)))
        count = max(1, int(sample_count))
        for index in range(count):
            timeline_ms = clip.start_ms + int(index * max(1, clip.duration_ms - 1) / max(1, count - 1))
            renderer.render_frame(composition, composition_time_ms(clip, composition, timeline_ms))
        return {"cached": count, "clip_id": clip.id, "composition_revision": composition.revision}

    def motion_clip_capture(self, *, clip_id: str, timeline_ms: int, output_path: str = "") -> dict[str, Any]:
        row = next((item for item in self._motion_clip_store() if str(item.get("id") or "") == clip_id), None)
        if row is None:
            raise ValueError(f"motion clip not found: {clip_id}")
        clip = MotionClip.from_dict(row)
        composition = self._motion_store().get(clip.composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {clip.composition_id}")
        output = Path(output_path) if output_path else Path(__file__).resolve().parents[2] / "debugCapture" / "motion_designer" / f"{clip.id}_{int(timeline_ms)}.png"
        from app.motion_designer.export_renderer import MotionExportRenderer
        path = MotionExportRenderer().save_png(composition, composition_time_ms(clip, composition, timeline_ms), output)
        return {"path": str(path), "clip_id": clip.id, "timeline_ms": int(timeline_ms)}
