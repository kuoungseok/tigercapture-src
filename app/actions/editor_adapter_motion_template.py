"""Motion Designer built-in template action adapter."""
from __future__ import annotations

from typing import Any, Mapping

from app.motion_designer.template_preview import render_template_preview
from app.motion_designer.templates import (
    apply_template_to_composition,
    get_template,
    list_templates,
    template_cost,
)


class MotionTemplateAdapterMixin:
    def motion_template_list(self) -> dict[str, Any]:
        rows = list_templates()
        return {"count": len(rows), "templates": rows}

    def motion_template_inspect(self, *, template_id: str) -> dict[str, Any]:
        return get_template(template_id).to_dict()

    def motion_template_apply(
        self,
        *,
        composition_id: str,
        template_id: str,
        variant: str = "",
        controls: Mapping[str, Any] | None = None,
        replace_existing: bool = True,
    ) -> dict[str, Any]:
        store = self._motion_store()
        composition = store.get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        candidate = apply_template_to_composition(
            composition,
            template_id,
            variant=variant,
            controls=controls,
            replace_existing=replace_existing,
        )
        template_state = candidate.metadata["last_applied_template"]
        instance_id = str(template_state["template_instance_id"])
        added = [
            layer
            for layer in candidate.layers
            if layer.metadata.get("template_instance_id") == instance_id
        ]
        removed_layer_ids = list(
            template_state.get("replaced_layer_ids") or []
        )
        store[composition_id] = candidate
        self._motion_sync_owner()
        return {
            "changed": bool(added or removed_layer_ids),
            "undo_label": "Apply Motion Template",
            "template_id": template_id,
            "variant": template_state["variant"],
            "added_layer_ids": [item.id for item in added],
            "removed_layer_ids": removed_layer_ids,
            "replace_existing": bool(replace_existing),
            "published_controls": template_state["published_controls"],
            "revision": candidate.revision,
        }

    def motion_template_preview(self, *, template_id: str, output_path: str,
                                variant: str = "16:9", controls: Mapping[str, Any] | None = None,
                                time_ms: float | None = None) -> dict[str, Any]:
        return render_template_preview(
            template_id, output_path, variant=variant, controls=controls, time_ms=time_ms,
        )

    def motion_template_cost(self, *, template_id: str, variant: str = "16:9",
                             controls: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return {"template_id": template_id, "variant": variant,
                **template_cost(template_id, variant=variant, controls=controls)}


__all__ = ["MotionTemplateAdapterMixin"]
