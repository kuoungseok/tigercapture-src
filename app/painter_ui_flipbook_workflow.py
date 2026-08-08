"""Pure Painter UI workflow for linked Motion flipbook bakes.

Qt UI code owns destination selection and user feedback.  This module owns the
stable-ID resolution, playback classification, deterministic bake, and safe
document attachment so automation and product UI cannot diverge.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from app.motion_designer.schema import MotionComposition
from app.motion_designer.ui_motion_binding import UIMotionBinding, ui_motion_bindings
from app.painter_ui_flipbook_bake import (
    PAINTER_UI_FLIPBOOK_MAX_ATLAS_SIZE,
    PLAYBACK_SCOPE_AMBIENT_LOOP,
    PLAYBACK_SCOPE_EVENT_TRIGGERED,
    PainterUIFlipbookBakeError,
    bake_motion_composition_flipbook,
)
from app.painter_ui_flipbook_document import (
    PAINTER_UI_FLIPBOOK_OBJECT_KINDS,
    PainterUIFlipbookAttachError,
    attach_flipbook_bake_to_painter_document,
)
from app.painter_ui_motion_bridge import linked_motion_binding_ref


PAINTER_UI_FLIPBOOK_WORKFLOW_SCHEMA = (
    "tigerstudio.painter.motion_flipbook_workflow.v1"
)
_STORAGE_SLUG_LIMIT = 48


class PainterUIFlipbookWorkflowError(ValueError):
    """A refused workflow with stable, machine-readable reasons."""

    def __init__(
        self,
        block_reasons: str | Sequence[str],
        *,
        detail: str = "",
    ) -> None:
        reasons = (
            [block_reasons]
            if isinstance(block_reasons, str)
            else [str(reason) for reason in block_reasons]
        )
        self.block_reasons = tuple(sorted(set(reasons)))
        self.detail = str(detail or "")
        message = ", ".join(self.block_reasons)
        if self.detail:
            message = f"{message}: {self.detail}"
        super().__init__(message)


def painter_ui_flipbook_storage_segment(value: object) -> str:
    """Encode an arbitrary stable ID as a readable Windows-safe segment."""
    raw = str(value or "").strip()
    if not raw:
        raise PainterUIFlipbookWorkflowError(
            "motion_flipbook_workflow_storage_id_missing"
        )
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", raw).strip("-_")
    slug = slug[:_STORAGE_SLUG_LIMIT].rstrip("-_") or "id"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"{slug}-{digest}"


def painter_ui_flipbook_output_directory(
    app_data_location: str | Path,
    document_id: object,
    object_id: object,
) -> Path:
    """Return a durable, traversal-safe AppData destination for one object."""
    raw_root = str(app_data_location or "").strip()
    if not raw_root:
        raise PainterUIFlipbookWorkflowError(
            "motion_flipbook_workflow_app_data_location_missing"
        )
    root = Path(raw_root).expanduser()
    if not root.is_absolute():
        raise PainterUIFlipbookWorkflowError(
            "motion_flipbook_workflow_app_data_location_not_absolute",
            detail=str(root),
        )
    try:
        resolved_root = root.resolve(strict=False)
        if any(part.casefold() == "debugcapture" for part in resolved_root.parts):
            raise PainterUIFlipbookWorkflowError(
                "motion_flipbook_workflow_app_data_location_disposable",
                detail=str(resolved_root),
            )
        output_dir = (
            resolved_root
            / "painter_ui_flipbooks"
            / painter_ui_flipbook_storage_segment(document_id)
            / painter_ui_flipbook_storage_segment(object_id)
        ).resolve(strict=False)
    except OSError as exc:
        raise PainterUIFlipbookWorkflowError(
            "motion_flipbook_workflow_output_directory_invalid",
            detail=f"{type(exc).__name__}:{exc}",
        ) from exc
    if resolved_root not in output_dir.parents:
        raise PainterUIFlipbookWorkflowError(
            "motion_flipbook_workflow_output_directory_outside_app_data",
            detail=str(output_dir),
        )
    return output_dir


def _selected_object_id(document: Mapping[str, Any], object_id: str) -> str:
    wanted = str(object_id or "")
    if wanted:
        return wanted
    selection = document.get("selection")
    selection = selection if isinstance(selection, Mapping) else {}
    wanted = str(selection.get("object_id") or "")
    if not wanted:
        raise PainterUIFlipbookWorkflowError(
            "motion_flipbook_workflow_selection_missing"
        )
    return wanted


def _target_object(document: Mapping[str, Any], object_id: str) -> dict[str, Any]:
    objects = document.get("objects")
    if not isinstance(objects, list):
        raise PainterUIFlipbookWorkflowError(
            "motion_flipbook_workflow_document_objects_invalid"
        )
    matches = [
        dict(row)
        for row in objects
        if isinstance(row, Mapping) and str(row.get("id") or "") == object_id
    ]
    if not matches:
        raise PainterUIFlipbookWorkflowError(
            f"motion_flipbook_workflow_object_missing:{object_id}"
        )
    if len(matches) > 1:
        raise PainterUIFlipbookWorkflowError(
            f"motion_flipbook_workflow_object_id_ambiguous:{object_id}"
        )
    kind = str(matches[0].get("kind") or "").strip().casefold()
    if kind not in PAINTER_UI_FLIPBOOK_OBJECT_KINDS:
        raise PainterUIFlipbookWorkflowError(
            f"motion_flipbook_workflow_object_kind_unsupported:{kind or 'unknown'}"
        )
    return matches[0]


def _composition(
    compositions: Mapping[str, MotionComposition | Mapping[str, Any]],
    composition_id: str,
) -> MotionComposition:
    value = compositions.get(composition_id)
    try:
        resolved = (
            MotionComposition.from_dict(value)
            if isinstance(value, Mapping)
            else value
        )
    except (TypeError, ValueError) as exc:
        raise PainterUIFlipbookWorkflowError(
            f"motion_flipbook_workflow_composition_invalid:{composition_id}",
            detail=f"{type(exc).__name__}:{exc}",
        ) from exc
    if not isinstance(resolved, MotionComposition):
        raise PainterUIFlipbookWorkflowError(
            f"motion_flipbook_workflow_composition_missing:{composition_id}"
        )
    return resolved


def _binding(
    composition: MotionComposition,
    *,
    object_id: str,
    binding_id: str,
) -> UIMotionBinding:
    bindings = ui_motion_bindings(composition)
    if binding_id:
        resolved = next((row for row in bindings if row.id == binding_id), None)
        if resolved is None:
            raise PainterUIFlipbookWorkflowError(
                f"motion_flipbook_workflow_binding_missing:{binding_id}"
            )
        if resolved.source_object_id != object_id:
            raise PainterUIFlipbookWorkflowError(
                f"motion_flipbook_workflow_binding_target_mismatch:{binding_id}"
            )
        return resolved
    resolved = next(
        (row for row in bindings if row.source_object_id == object_id),
        None,
    )
    if resolved is None:
        raise PainterUIFlipbookWorkflowError(
            f"motion_flipbook_workflow_binding_missing:{object_id}"
        )
    return resolved


def _interaction_trigger_ids(
    document: Mapping[str, Any],
    *,
    object_id: str,
    composition_id: str,
    binding_id: str,
) -> tuple[str, ...]:
    interactions = document.get("interactions")
    if not isinstance(interactions, list):
        return ()
    accepted_refs = {composition_id, binding_id}
    return tuple(
        sorted(
            {
                str(row.get("id") or f"interaction-{index}")
                for index, row in enumerate(interactions)
                if isinstance(row, Mapping)
                and bool(row.get("enabled", True))
                and str(row.get("source_object_id") or "") == object_id
                and str(row.get("action") or "").strip().casefold()
                == "play_animation"
                and str(row.get("motion_clip_id") or "") in accepted_refs
            }
        )
    )


def classify_flipbook_playback_scope(
    binding: UIMotionBinding,
    *,
    interaction_trigger_ids: Sequence[str] = (),
) -> str:
    """Return ambient only for a true untriggered autoplaying loop."""
    if (
        bool(binding.autoplay)
        and bool(binding.loop)
        and not str(binding.trigger or "").strip()
        and not tuple(interaction_trigger_ids)
    ):
        return PLAYBACK_SCOPE_AMBIENT_LOOP
    return PLAYBACK_SCOPE_EVENT_TRIGGERED


def bake_linked_motion_flipbook(
    document: Mapping[str, Any],
    compositions: Mapping[str, MotionComposition | Mapping[str, Any]],
    output_dir: str | Path,
    *,
    object_id: str = "",
    fps: float | None = None,
    frame_count: int | None = None,
    cell_width: int | None = None,
    cell_height: int | None = None,
    max_atlas_size: int = PAINTER_UI_FLIPBOOK_MAX_ATLAS_SIZE,
    renderer: Any = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Bake and attach the selected image/rectangle's linked composition."""
    if not isinstance(document, Mapping):
        raise PainterUIFlipbookWorkflowError(
            "motion_flipbook_workflow_document_invalid"
        )
    wanted_id = _selected_object_id(document, object_id)
    target = _target_object(document, wanted_id)
    ref = linked_motion_binding_ref(document, wanted_id)
    composition_id = str(ref.get("composition_id") or "")
    if not composition_id:
        raise PainterUIFlipbookWorkflowError(
            f"motion_flipbook_workflow_binding_link_missing:{wanted_id}"
        )
    composition = _composition(compositions, composition_id)
    binding = _binding(
        composition,
        object_id=wanted_id,
        binding_id=str(ref.get("binding_id") or ""),
    )
    interaction_ids = _interaction_trigger_ids(
        document,
        object_id=wanted_id,
        composition_id=composition.id,
        binding_id=binding.id,
    )
    playback_scope = classify_flipbook_playback_scope(
        binding,
        interaction_trigger_ids=interaction_ids,
    )
    try:
        bake = bake_motion_composition_flipbook(
            composition,
            output_dir,
            fps=fps,
            frame_count=frame_count,
            cell_width=cell_width,
            cell_height=cell_height,
            max_atlas_size=max_atlas_size,
            playback_scope=playback_scope,
            loop=bool(binding.loop),
            renderer=renderer,
        )
        updated, attachment = attach_flipbook_bake_to_painter_document(
            document,
            wanted_id,
            bake,
        )
    except (PainterUIFlipbookBakeError, PainterUIFlipbookAttachError) as exc:
        raise PainterUIFlipbookWorkflowError(
            exc.block_reasons,
            detail=exc.detail,
        ) from exc

    report = {
        "schema": PAINTER_UI_FLIPBOOK_WORKFLOW_SCHEMA,
        "ok": True,
        "changed": bool(attachment["changed"]),
        "idempotent_reuse": bool(attachment["idempotent_reuse"]),
        "document_id": str(document.get("document_id") or ""),
        "input_revision": int(attachment["input_revision"]),
        "result_revision": int(attachment["result_revision"]),
        "object_id": wanted_id,
        "object_kind": str(target.get("kind") or "").strip().casefold(),
        "composition_id": composition.id,
        "composition_revision": int(composition.revision),
        "binding_id": binding.id,
        "playback_scope": playback_scope,
        "playback_decision": {
            "autoplay": bool(binding.autoplay),
            "loop": bool(binding.loop),
            "binding_trigger": str(binding.trigger or ""),
            "interaction_trigger_ids": list(interaction_ids),
            "ambient_requires": "autoplay_and_loop_without_interaction_trigger",
        },
        "material_ready": bool(bake.material_ready),
        "block_reasons": list(bake.block_reasons),
        "atlas_path": str(bake.atlas_path),
        "manifest_path": str(bake.manifest_path),
        "bake_reused": bool(bake.reused),
        "shader_policy": {
            "generator": str(bake.flipbook_record.get("Generator") or ""),
            "arbitrary_hlsl": "forbidden",
        },
        "attachment": attachment,
    }
    return updated, report


__all__ = [
    "PAINTER_UI_FLIPBOOK_WORKFLOW_SCHEMA",
    "PainterUIFlipbookWorkflowError",
    "bake_linked_motion_flipbook",
    "classify_flipbook_playback_scope",
    "painter_ui_flipbook_output_directory",
    "painter_ui_flipbook_storage_segment",
]
