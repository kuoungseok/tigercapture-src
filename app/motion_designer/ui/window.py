from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QElapsedTimer, QThread, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QDockWidget, QFileDialog, QListWidget, QMainWindow, QSplitter, QTabWidget,
    QVBoxLayout, QWidget,
)

from app.motion_designer.ai_workspace import build_motion_ai_proposal, apply_motion_ai_proposal
from app.motion_designer.commands import find_layer, set_keyframe
from app.motion_designer.composition_service import CompositionService
from app.motion_designer.schema import (
    AnimatedProperty, Keyframe, MotionBehaviorRef, MotionComposition,
    MotionEffectRef, MotionLayer, MotionMaskRef, SourceRef,
)
from app.motion_designer.vector_shapes import default_pen_path

from .behavior_panel import BehaviorPanel
from .ai_panel import MotionAIPanel
from .canvas import MotionCanvas
from .effect_mask_panel import EffectMaskPanel
from .inspector import InspectorPanel
from .layer_panel import LayerPanel
from .library_panel import MotionLibraryPanel
from .style import MOTION_DESIGNER_QSS
from .timeline import MotionTimeline
from .toolbar import MotionToolbar
from .tracking_worker import MotionTrackingWorker
from .typography_panel import TypographyPanel
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

    def update_keyframe(
        self, layer_id: str, property_name: str, keyframe_id: str, time_ms: int, value,
    ) -> None:
        candidate = MotionComposition.from_dict(self.composition.to_dict())
        layer = find_layer(candidate, layer_id)
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


class MotionDesignerWindow(QMainWindow):
    composition_changed = Signal(object)
    autosave_requested = Signal(object)

    def __init__(self, composition: MotionComposition | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("MotionDesignerWindow")
        self.setWindowTitle("Motion Designer")
        self.resize(1520, 900)
        self.setStyleSheet(MOTION_DESIGNER_QSS)
        self._selected_layer_id = ""
        self._time_ms = 0
        self._play_direction = 0
        self._loop_playback = False
        self._play_clock = QElapsedTimer()
        self._tracking_jobs: dict[str, tuple[QThread, MotionTrackingWorker, str]] = {}
        self.controller = MotionDocumentController(composition or MotionComposition(), self._on_model_changed)

        self.toolbar = MotionToolbar(self)
        self.addToolBar(self.toolbar)
        self.library = MotionLibraryPanel(self)
        self.layers = LayerPanel(self)
        self.media = QListWidget(self)
        self.audio = QListWidget(self)
        self.inspector = InspectorPanel(self)
        self.vector = VectorPanel(self)
        self.typography = TypographyPanel(self)
        self.behaviors = BehaviorPanel(self)
        self.effects = EffectMaskPanel("effect", self)
        self.masks = EffectMaskPanel("mask", self)
        self.inspector_tabs = QTabWidget(self)
        self.inspector_tabs.addTab(self.inspector, "Properties")
        self.inspector_tabs.addTab(self.vector, "Shape")
        self.inspector_tabs.addTab(self.typography, "Text")
        self.inspector_tabs.addTab(self.behaviors, "Behaviors")
        self.inspector_tabs.addTab(self.effects, "Filters")
        self.inspector_tabs.addTab(self.masks, "Masks")
        self.left_tabs = QTabWidget(self)
        self.left_tabs.addTab(self.library, "Library")
        self.left_tabs.addTab(self.inspector_tabs, "Inspector")
        self.project_tabs = QTabWidget(self)
        self.project_tabs.addTab(self.layers, "Layers")
        self.project_tabs.addTab(self.media, "Media")
        self.project_tabs.addTab(self.audio, "Audio")

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
        production = QSplitter(Qt.Vertical, self)
        production.addWidget(viewer)
        production.addWidget(self.timeline)
        production.setSizes([560, 300])
        production.setCollapsible(0, False)
        workspace = QSplitter(Qt.Horizontal, self)
        workspace.setObjectName("MotionWorkspace")
        workspace.addWidget(self.left_tabs)
        workspace.addWidget(self.project_tabs)
        workspace.addWidget(production)
        workspace.setSizes([280, 250, 990])
        workspace.setStretchFactor(2, 1)
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

        self.toolbar.add_layer_requested.connect(self._add_layer)
        self.toolbar.behavior_requested.connect(self._add_behavior)
        self.toolbar.effect_requested.connect(self._add_effect)
        self.toolbar.delete_requested.connect(self._delete_selected)
        self.toolbar.duplicate_requested.connect(self._duplicate_selected)
        self.toolbar.undo_requested.connect(self.controller.undo)
        self.toolbar.redo_requested.connect(self.controller.redo)
        self.toolbar.ai_toggled.connect(self.ai_dock.setVisible)
        self.ai_dock.visibilityChanged.connect(self.toolbar.set_ai_visible)
        self.layers.layer_selected.connect(self._select_layer)
        self.layers.layer_flags_changed.connect(self._update_layer_flags)
        self.layers.layer_structure_changed.connect(self.controller.apply_layer_structure)
        self.canvas.layer_selected.connect(self._select_layer)
        self.canvas.layer_moved.connect(self._move_layer)
        self.canvas.vector_path_changed.connect(self._set_vector_path)
        self.canvas.typography_path_changed.connect(self._set_typography_path)
        self.canvas.typography_path_offset_changed.connect(self._set_typography_path_offset)
        self.inspector.property_changed.connect(self._set_inspector_property)
        self.inspector.keyframe_requested.connect(self._set_keyframe)
        self.vector.source_changed.connect(self._set_vector_params)
        self.typography.source_changed.connect(self._set_typography_params)
        self.library.apply_requested.connect(self._apply_library_item)
        self.behaviors.add_requested.connect(self._add_behavior)
        self.behaviors.delete_requested.connect(self._delete_behavior)
        self.behaviors.parameter_changed.connect(self._set_behavior_param)
        self.effects.add_requested.connect(self._add_effect)
        self.effects.delete_requested.connect(self._delete_effect)
        self.effects.parameter_changed.connect(self._set_effect_param)
        self.masks.add_requested.connect(self._add_mask)
        self.masks.delete_requested.connect(self._delete_mask)
        self.masks.parameter_changed.connect(self._set_mask_param)
        self.masks.item_changed.connect(self._set_mask_item)
        self.masks.tracking_requested.connect(self._start_mask_tracking)
        self.masks.tracking_cancel_requested.connect(self._cancel_mask_tracking)
        self.timeline.time_changed.connect(self._set_time)
        self.timeline.playback_requested.connect(self._set_playback_direction)
        self.timeline.loop_changed.connect(self._set_loop_playback)
        self.timeline.layer_selected.connect(self._select_layer)
        self.timeline.layer_timing_changed.connect(self._set_layer_timing)
        self.timeline.keyframe_changed.connect(self.controller.update_keyframe)
        self.viewer_header.zoom_changed.connect(self.canvas.set_zoom_mode)
        self.viewer_header.grid_changed.connect(self.canvas.set_grid_visible)
        self.viewer_header.safe_changed.connect(self.canvas.set_safe_guides_visible)
        self.ai.plan_requested.connect(self._plan_ai_request)
        self.ai.apply_requested.connect(self._apply_ai_proposal)

        self._play_timer = QTimer(self)
        self._play_timer.setInterval(16)
        self._play_timer.timeout.connect(self._tick)
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(30000)
        self._autosave_timer.timeout.connect(lambda: self.autosave_requested.emit(self.controller.composition))
        self._autosave_timer.start()
        self._on_model_changed(self.controller.composition)

    def _on_model_changed(self, composition: MotionComposition) -> None:
        self.canvas.set_composition(composition, self._time_ms)
        self.preview.set_composition(composition, self._time_ms)
        self.layers.set_composition(composition)
        self.timeline.set_composition(composition, self._time_ms)
        self.viewer_header.set_fps(composition.fps)
        self._update_media_panel(composition)
        self.composition_changed.emit(composition)
        if self._selected_layer_id:
            self._select_layer(self._selected_layer_id)

    def _add_layer(self, layer_type: str) -> None:
        composition = self.controller.composition
        requested_type = str(layer_type or "shape")
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
        self._selected_layer_id = str(layer_id or "")
        layer = next((item for item in self.controller.composition.layers if item.id == self._selected_layer_id), None)
        self.inspector.set_layer(layer)
        self.vector.set_layer(layer, self.controller.composition)
        self.typography.set_layer(layer)
        self.behaviors.set_layer(layer)
        self.effects.set_layer(layer)
        self.masks.set_layer(layer)
        self.timeline.set_selected_layer(self._selected_layer_id)
        self.canvas.set_selected_layer(self._selected_layer_id)
        if layer is not None:
            self.layers.select_layer(layer.id)

    def _apply_library_item(self, domain: str, kind: str) -> None:
        if domain == "object":
            self._add_layer(kind)
        elif domain == "behavior":
            self._add_behavior(kind)
            self.left_tabs.setCurrentWidget(self.inspector_tabs)
            self.inspector_tabs.setCurrentWidget(self.behaviors)
        elif domain == "effect":
            self._add_effect(kind)
            self.left_tabs.setCurrentWidget(self.inspector_tabs)
            self.inspector_tabs.setCurrentWidget(self.effects)

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

    def _plan_ai_request(self, payload: object) -> None:
        values = payload if isinstance(payload, dict) else {}
        proposal = build_motion_ai_proposal(
            self.controller.composition,
            prompt=str(values.get("prompt") or ""),
            references=values.get("references") or [],
            provider=str(values.get("provider") or "local_layout"),
        )
        self.ai.set_proposal(proposal.to_dict())

    def _apply_ai_proposal(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return
        candidate = apply_motion_ai_proposal(self.controller.composition, payload)
        added_ids = [item.id for item in candidate.layers[len(self.controller.composition.layers):]]
        self.controller.replace(candidate)
        if added_ids:
            self._select_layer(added_ids[-1])
        self.ai.set_applied(len(added_ids))

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
        defaults = {
            "brightness_contrast": {"brightness": 0.0, "contrast": 1.0},
            "saturation": {"amount": 1.0}, "gaussian_blur": {"radius": 4.0},
            "glow": {"threshold": .7, "radius": 8.0, "intensity": .7},
            "unsharp_mask": {"radius": 2.0, "amount": .75},
            "vignette": {"amount": .35, "softness": .65},
        }
        effect = MotionEffectRef(kind=kind, params={
            key: AnimatedProperty(default=value) for key, value in defaults.get(kind, {}).items()
        })
        self.controller.update_layer(layer.id, {"effects": [*[item.to_dict() for item in layer.effects], effect.to_dict()]})

    def _delete_effect(self, effect_id: str) -> None:
        layer = find_layer(self.controller.composition, self._selected_layer_id)
        self.controller.update_layer(layer.id, {"effects": [item.to_dict() for item in layer.effects if item.id != effect_id]})

    def _set_effect_param(self, effect_id: str, key: str, value: float) -> None:
        layer = find_layer(self.controller.composition, self._selected_layer_id)
        effects = [item.to_dict() for item in layer.effects]
        for item in effects:
            if item["id"] == effect_id:
                item.setdefault("params", {})[key] = AnimatedProperty(default=value).to_dict()
        self.controller.update_layer(layer.id, {"effects": effects})

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
        masks = [item.to_dict() for item in layer.masks]
        for item in masks:
            if item["id"] == mask_id:
                item.setdefault("params", {})[key] = AnimatedProperty(default=value).to_dict()
        self.controller.update_layer(layer.id, {"masks": masks})

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
        self.controller.update_layer(layer.id, {"masks": masks})

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

    def _set_time(self, time_ms: int) -> None:
        self._time_ms = int(time_ms)
        self.canvas.set_time(self._time_ms)
        self.preview.set_time(self._time_ms)
        self.timeline.tracks.set_state(self.controller.composition, self._time_ms)

    def _set_playing(self, playing: bool) -> None:
        self._set_playback_direction(1 if playing else 0)

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
        elapsed_ms = self._play_clock.restart() if self._play_clock.isValid() else self._play_timer.interval()
        self._advance_playback(max(1, min(100, int(elapsed_ms))))

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
        for thread, worker, _layer_id in list(self._tracking_jobs.values()):
            worker.cancel()
            thread.quit()
        for thread, _worker, _layer_id in list(self._tracking_jobs.values()):
            thread.wait(5000)
        super().closeEvent(event)
