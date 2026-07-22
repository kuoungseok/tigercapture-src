"""Shared mutation service used by UI and automation actions."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .schema import MotionComposition, MotionLayer, new_motion_id
from .validation import ValidationReport, validate_all, validate_composition


class MotionServiceError(ValueError):
    pass


@dataclass(slots=True)
class MutationResult:
    changed: bool
    undo_label: str
    payload: dict[str, Any]
    validation: ValidationReport

    def to_dict(self) -> dict[str, Any]:
        return {"changed": self.changed, "undo_label": self.undo_label, "payload": self.payload,
                "validation": self.validation.to_dict()}


class CompositionService:
    def __init__(self, compositions: Iterable[MotionComposition | Mapping[str, Any]] = ()) -> None:
        self._items: list[MotionComposition] = [
            item if isinstance(item, MotionComposition) else MotionComposition.from_dict(item)
            for item in compositions
        ]
        report = validate_all(self._items)
        if not report.ok:
            raise MotionServiceError(report.issues[0].message)

    def list(self) -> list[MotionComposition]:
        return list(self._items)

    def as_dicts(self) -> list[dict[str, Any]]:
        return [item.to_dict() for item in self._items]

    def get(self, composition_id: str) -> MotionComposition:
        for item in self._items:
            if item.id == composition_id:
                return item
        raise MotionServiceError(f"Unknown composition: {composition_id}")

    def create(self, *, name: str = "Motion Composition", width: int = 1920, height: int = 1080,
               fps: float = 30.0, duration_ms: int = 5000, dry_run: bool = False) -> MutationResult:
        item = MotionComposition(name=name, width=width, height=height, fps=fps, duration_ms=duration_ms)
        report = validate_composition(item)
        if report.ok and not dry_run:
            self._items.append(item)
        return MutationResult(not dry_run and report.ok, "Create Motion Composition", {"composition": item.to_dict()}, report)

    def update(self, composition_id: str, changes: Mapping[str, Any], *, dry_run: bool = False) -> MutationResult:
        current = self.get(composition_id)
        data = current.to_dict()
        allowed = {"name", "width", "height", "fps", "duration_ms", "metadata"}
        data.update({key: deepcopy(value) for key, value in changes.items() if key in allowed})
        candidate = MotionComposition.from_dict(data)
        candidate.revision = current.revision + 1
        report = validate_composition(candidate)
        if report.ok and not dry_run:
            self._items[self._items.index(current)] = candidate
        return MutationResult(not dry_run and report.ok, "Update Motion Composition", {"composition": candidate.to_dict()}, report)

    def duplicate(self, composition_id: str, *, dry_run: bool = False) -> MutationResult:
        candidate = self.get(composition_id).clone()
        report = validate_composition(candidate)
        if report.ok and not dry_run:
            self._items.append(candidate)
        return MutationResult(not dry_run and report.ok, "Duplicate Motion Composition", {"composition": candidate.to_dict()}, report)

    def delete(self, composition_id: str, *, dry_run: bool = False) -> MutationResult:
        item = self.get(composition_id)
        if not dry_run:
            self._items.remove(item)
        return MutationResult(not dry_run, "Delete Motion Composition", {"composition_id": composition_id}, ValidationReport())

    def add_layer(self, composition_id: str, layer: MotionLayer | Mapping[str, Any], *, index: int | None = None,
                  dry_run: bool = False) -> MutationResult:
        current = self.get(composition_id)
        candidate = MotionComposition.from_dict(current.to_dict())
        new_layer = layer if isinstance(layer, MotionLayer) else MotionLayer.from_dict(layer)
        if any(item.id == new_layer.id for item in candidate.layers):
            new_layer = MotionLayer.from_dict({**new_layer.to_dict(), "id": new_motion_id("layer")})
        insert_at = len(candidate.layers) if index is None else max(0, min(int(index), len(candidate.layers)))
        candidate.layers.insert(insert_at, new_layer)
        candidate.revision += 1
        return self._commit_candidate(current, candidate, "Add Motion Layer", dry_run)

    def update_layer(self, composition_id: str, layer_id: str, changes: Mapping[str, Any], *, dry_run: bool = False) -> MutationResult:
        current = self.get(composition_id)
        candidate = MotionComposition.from_dict(current.to_dict())
        layer = next((item for item in candidate.layers if item.id == layer_id), None)
        if layer is None:
            raise MotionServiceError(f"Unknown layer: {layer_id}")
        data = layer.to_dict()
        data.update(deepcopy(dict(changes)))
        candidate.layers[candidate.layers.index(layer)] = MotionLayer.from_dict(data)
        candidate.revision += 1
        return self._commit_candidate(current, candidate, "Update Motion Layer", dry_run)

    def delete_layer(self, composition_id: str, layer_id: str, *, dry_run: bool = False) -> MutationResult:
        current = self.get(composition_id)
        candidate = MotionComposition.from_dict(current.to_dict())
        if not any(item.id == layer_id for item in candidate.layers):
            raise MotionServiceError(f"Unknown layer: {layer_id}")
        candidate.layers = [item for item in candidate.layers if item.id != layer_id]
        for layer in candidate.layers:
            if layer.parent_id == layer_id:
                layer.parent_id = ""
        candidate.revision += 1
        return self._commit_candidate(current, candidate, "Delete Motion Layer", dry_run)

    def duplicate_layer(self, composition_id: str, layer_id: str, *, dry_run: bool = False) -> MutationResult:
        current = self.get(composition_id)
        candidate = MotionComposition.from_dict(current.to_dict())
        source = next((item for item in candidate.layers if item.id == layer_id), None)
        if source is None:
            raise MotionServiceError(f"Unknown layer: {layer_id}")
        data = source.to_dict()
        data["id"] = new_motion_id("layer")
        data["name"] = f"{source.name} Copy"
        duplicate = MotionLayer.from_dict(data)
        candidate.layers.insert(candidate.layers.index(source) + 1, duplicate)
        candidate.revision += 1
        return self._commit_candidate(current, candidate, "Duplicate Motion Layer", dry_run)

    def reorder_layer(self, composition_id: str, layer_id: str, index: int, *, dry_run: bool = False) -> MutationResult:
        current = self.get(composition_id)
        candidate = MotionComposition.from_dict(current.to_dict())
        layer = next((item for item in candidate.layers if item.id == layer_id), None)
        if layer is None:
            raise MotionServiceError(f"Unknown layer: {layer_id}")
        candidate.layers.remove(layer)
        candidate.layers.insert(max(0, min(int(index), len(candidate.layers))), layer)
        candidate.revision += 1
        return self._commit_candidate(current, candidate, "Reorder Motion Layer", dry_run)

    def parent_layer(self, composition_id: str, layer_id: str, parent_id: str = "", *, dry_run: bool = False) -> MutationResult:
        return self.update_layer(composition_id, layer_id, {"parent_id": parent_id}, dry_run=dry_run)

    def _commit_candidate(self, current: MotionComposition, candidate: MotionComposition, label: str,
                          dry_run: bool) -> MutationResult:
        report = validate_composition(candidate)
        if report.ok and not dry_run:
            self._items[self._items.index(current)] = candidate
        return MutationResult(not dry_run and report.ok, label, {"composition": candidate.to_dict()}, report)
