"""Motion Designer structured-expression action adapter."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from typing import Any, Mapping

from app.motion_designer.composition_service import CompositionService
from app.motion_designer.expressions import (
    EXPRESSION_KEY,
    bake_procedural_transform,
    clear_layer_expression,
    expression_issues,
    layer_expressions,
    set_layer_expression,
)
from app.motion_designer.schema import MotionComposition


class MotionExpressionAdapterMixin:
    def motion_expression_list(self, *, composition_id: str, layer_id: str = "") -> dict[str, Any]:
        composition = self._motion_store().get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        rows = []
        for layer in composition.layers:
            if layer_id and layer.id != layer_id:
                continue
            for property_name, expression in layer_expressions(layer).items():
                rows.append({"layer_id": layer.id, "property_name": property_name, "expression": deepcopy(expression)})
        return {"count": len(rows), "expressions": rows}

    def motion_expression_set(self, *, composition_id: str, layer_id: str,
                              property_name: str, expression: Any) -> dict[str, Any]:
        service = CompositionService(self._motion_store().values())
        current = service.get(composition_id)
        candidate = MotionComposition.from_dict(current.to_dict())
        layer = next((item for item in candidate.layers if item.id == layer_id), None)
        if layer is None:
            raise ValueError(f"motion layer not found: {layer_id}")
        set_layer_expression(layer, property_name, deepcopy(expression))
        candidate.revision += 1
        result = service.update_layer(
            composition_id, layer_id, {"metadata": candidate.layers[candidate.layers.index(layer)].metadata},
        )
        if not result.validation.ok:
            return {"changed": False, "undo_label": "Set Motion Expression",
                    "validation": result.validation.to_dict()}
        self._motion_commit(service)
        return {"changed": True, "undo_label": "Set Motion Expression",
                "property_name": str(property_name), "expression": deepcopy(expression),
                "validation": result.validation.to_dict()}

    def motion_expression_clear(self, *, composition_id: str, layer_id: str,
                                property_name: str = "") -> dict[str, Any]:
        service = CompositionService(self._motion_store().values())
        composition = service.get(composition_id)
        layer = next((item for item in composition.layers if item.id == layer_id), None)
        if layer is None:
            raise ValueError(f"motion layer not found: {layer_id}")
        metadata = deepcopy(layer.metadata)
        draft = MotionComposition.from_dict(composition.to_dict())
        draft_layer = next(item for item in draft.layers if item.id == layer_id)
        removed = clear_layer_expression(draft_layer, property_name)
        if not removed:
            return {"changed": False, "undo_label": "Clear Motion Expression", "removed": 0}
        metadata = draft_layer.metadata
        result = service.update_layer(composition_id, layer_id, {"metadata": metadata})
        self._motion_commit(service)
        return {"changed": True, "undo_label": "Clear Motion Expression", "removed": removed,
                "validation": result.validation.to_dict()}

    def motion_expression_validate(self, *, composition_id: str) -> dict[str, Any]:
        composition = self._motion_store().get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        rows = [asdict(issue) for issue in expression_issues(composition)]
        return {"ok": not rows, "issues": rows}

    def motion_expression_bake(self, *, composition_id: str, layer_id: str,
                               sample_fps: float = 30.0) -> dict[str, Any]:
        composition = self._motion_store().get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        result = bake_procedural_transform(composition, layer_id, sample_fps=sample_fps)
        return {"changed": bool(result["keyframes"]), "undo_label": "Bake Motion Procedural Transform", **result,
                "revision": composition.revision}


__all__ = ["MotionExpressionAdapterMixin"]
