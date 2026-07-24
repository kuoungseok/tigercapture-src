"""Action adapter for validated Motion Designer AI generation and patches."""
from __future__ import annotations

from typing import Any, Mapping


class MotionAIGenerationAdapterMixin:
    def motion_ai_provider_status(self) -> dict[str, Any]:
        from app.motion_designer.ai_generation import motion_ai_provider_status

        return motion_ai_provider_status()

    def motion_ai_reference_analyze(self, references: list[Mapping[str, Any]] | None = None) -> dict[str, Any]:
        from app.motion_designer.ai_workspace import MotionAIReference

        rows: list[dict[str, Any]] = []
        for raw in references or []:
            item = MotionAIReference.from_dict(raw)
            row = {
                "id": item.id,
                "kind": item.kind,
                "name": item.name,
                "uri": item.uri,
                "mime_type": item.mime_type,
                "role": str(item.metadata.get("role") or "auto"),
                "metadata": dict(item.metadata),
            }
            if item.kind == "text":
                row.update({"character_count": len(item.text), "preview": item.text[:240]})
            else:
                from pathlib import Path

                path = Path(item.uri) if item.uri and not item.uri.startswith(("http://", "https://")) else None
                row["available"] = bool(path and path.is_file())
                if path and path.is_file():
                    try:
                        from PIL import Image

                        with Image.open(path) as image:
                            row.update({
                                "width": int(image.width),
                                "height": int(image.height),
                                "mode": str(image.mode),
                                "has_alpha": "A" in image.getbands(),
                            })
                    except Exception as exc:
                        row["probe_warning"] = str(exc)
            rows.append(row)
        return {
            "count": len(rows),
            "references": rows,
            "semantic_vision_used": False,
            "note": "This stage probes local asset facts; the selected planner assigns editable roles.",
        }

    def motion_ai_reference_decompose(
        self,
        *,
        source_path: str,
        width: int,
        height: int,
        max_elements: int = 5,
        include_depth: bool = True,
        segmentation_mode: str = "auto",
        point_hints: list[list[float]] | None = None,
        object_hints: list[Mapping[str, Any]] | None = None,
        inpaint_mode: str = "auto",
        reconstruct_text: bool = True,
        ocr_native_threshold: float = 0.78,
        force: bool = False,
    ) -> dict[str, Any]:
        from app.motion_designer.image_decomposition import decompose_image

        return decompose_image(
            source_path,
            width=width,
            height=height,
            max_elements=max_elements,
            include_depth=include_depth,
            segmentation_mode=segmentation_mode,
            point_hints=point_hints or (),
            object_hints=object_hints or (),
            inpaint_mode=inpaint_mode,
            reconstruct_text=reconstruct_text,
            ocr_native_threshold=ocr_native_threshold,
            force=force,
        ).to_dict()

    def motion_ai_layer_analyze(self, **params: Any) -> dict[str, Any]:
        return self.motion_ai_reference_decompose(**params)

    def motion_ai_layer_segment(self, **params: Any) -> dict[str, Any]:
        return self.motion_ai_reference_decompose(**params)

    def motion_ai_layer_mask_refine(self, **params: Any) -> dict[str, Any]:
        values = dict(params)
        values["segmentation_mode"] = "sam"
        values["force"] = True
        return self.motion_ai_reference_decompose(**values)

    def motion_ai_layer_merge(
        self,
        *,
        decomposition: Mapping[str, Any],
        element_ids: list[str],
    ) -> dict[str, Any]:
        from app.motion_designer.image_decomposition_edits import (
            merge_decomposition_elements,
        )

        return merge_decomposition_elements(decomposition, element_ids).to_dict()

    def motion_ai_layer_mask_replace(
        self,
        *,
        decomposition: Mapping[str, Any],
        element_id: str,
        mask_path: str,
    ) -> dict[str, Any]:
        from app.motion_designer.image_decomposition_edits import (
            replace_decomposition_element_mask,
        )

        return replace_decomposition_element_mask(
            decomposition,
            element_id,
            mask_path,
        ).to_dict()

    def motion_ai_layer_split(
        self,
        *,
        decomposition: Mapping[str, Any],
        element_id: str,
        axis: str,
        position: float,
    ) -> dict[str, Any]:
        from app.motion_designer.image_decomposition_edits import (
            split_decomposition_element,
        )

        return split_decomposition_element(
            decomposition,
            element_id,
            axis=axis,
            position=position,
        ).to_dict()

    def motion_ai_layer_lock(
        self,
        *,
        decomposition: Mapping[str, Any],
        element_ids: list[str],
        locked: bool,
    ) -> dict[str, Any]:
        from app.motion_designer.image_decomposition_edits import (
            set_decomposition_lock,
        )

        return set_decomposition_lock(
            decomposition,
            element_ids,
            locked=locked,
        ).to_dict()

    def motion_ai_layer_group(
        self,
        *,
        decomposition: Mapping[str, Any],
        child_ids: list[str],
        parent_id: str = "",
    ) -> dict[str, Any]:
        from app.motion_designer.image_decomposition_edits import (
            set_decomposition_parent,
        )

        return set_decomposition_parent(
            decomposition,
            child_ids,
            parent_id=parent_id,
        ).to_dict()

    def motion_ai_layer_pivot(
        self,
        *,
        decomposition: Mapping[str, Any],
        element_id: str,
        pivot: list[float],
    ) -> dict[str, Any]:
        from app.motion_designer.image_decomposition_edits import (
            set_decomposition_pivot,
        )

        return set_decomposition_pivot(
            decomposition,
            element_id,
            pivot=pivot,
        ).to_dict()

    def motion_ai_layer_order(
        self,
        *,
        decomposition: Mapping[str, Any],
        element_id: str,
        z_order: int,
    ) -> dict[str, Any]:
        from app.motion_designer.image_decomposition_edits import (
            set_decomposition_z_order,
        )

        return set_decomposition_z_order(
            decomposition,
            element_id,
            z_order=z_order,
        ).to_dict()

    def motion_ai_background_inpaint(self, **params: Any) -> dict[str, Any]:
        return self.motion_ai_reference_decompose(**params)

    def motion_ai_text_reconstruct(self, **params: Any) -> dict[str, Any]:
        values = dict(params)
        values["reconstruct_text"] = True
        return self.motion_ai_reference_decompose(**values)

    def motion_ai_choreography_plan(
        self,
        *,
        decomposition: Mapping[str, Any],
        duration_ms: int,
        variant: str = "auto",
        prompt: str = "",
        motion_style: str = "",
        audio_hits_ms: list[int] | None = None,
    ) -> dict[str, Any]:
        from app.motion_designer.image_decomposition import ImageDecompositionResult
        from app.motion_designer.motion_choreography import plan_motion_choreography

        result = ImageDecompositionResult.from_dict(decomposition)
        inpaint = (
            result.diagnostics.get("inpaint")
            if isinstance(result.diagnostics.get("inpaint"), Mapping)
            else {}
        )
        return plan_motion_choreography(
            result.elements,
            duration_ms=duration_ms,
            max_camera_travel_ratio=float(
                inpaint.get("max_camera_travel_ratio", 0.0)
            ),
            requested_variant=variant,
            prompt=prompt,
            motion_style=motion_style,
            audio_hits_ms=audio_hits_ms or (),
        ).to_dict()

    def motion_ai_integrity_validate(
        self,
        *,
        decomposition: Mapping[str, Any],
    ) -> dict[str, Any]:
        from app.motion_designer.image_decomposition import ImageDecompositionResult
        from app.motion_designer.image_motion_validation import (
            validate_decomposition_result,
        )

        result = ImageDecompositionResult.from_dict(decomposition)
        return validate_decomposition_result(result).to_dict()

    def motion_ai_choreography_apply(
        self,
        *,
        composition_id: str,
        decomposition: Mapping[str, Any],
        in_ms: int,
        out_ms: int,
        reference_id: str = "layered_image",
        name: str = "Layered Image",
        center: list[float] | None = None,
        size: list[int] | None = None,
        variant: str = "auto",
        prompt: str = "",
        motion_style: str = "",
        audio_hits_ms: list[int] | None = None,
        base_revision: int | None = None,
    ) -> dict[str, Any]:
        from app.motion_designer.image_decomposition import (
            ImageDecompositionResult,
            compile_decomposition_layers,
        )
        from app.motion_designer.schema import MotionComposition

        store = self._motion_store()
        composition = store.get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        if base_revision is not None and int(base_revision) != composition.revision:
            raise ValueError("stale composition revision")
        target = MotionComposition.from_dict(composition.to_dict())
        target_center = center or [target.width / 2.0, target.height / 2.0]
        target_size = size or [target.width, target.height]
        layers = compile_decomposition_layers(
            target,
            ImageDecompositionResult.from_dict(decomposition),
            reference_id=reference_id,
            name=name,
            in_ms=in_ms,
            out_ms=out_ms,
            center=(float(target_center[0]), float(target_center[1])),
            size=(int(target_size[0]), int(target_size[1])),
            motion_style=motion_style,
            motion_variant=variant,
            prompt=prompt,
            audio_hits_ms=audio_hits_ms or (),
        )
        if not layers:
            raise ValueError("decomposition did not compile into Motion layers")
        target.layers.extend(layers)
        target.revision = composition.revision + 1
        store[composition_id] = target
        self._motion_sync_owner()
        return {
            "changed": True,
            "undo_label": "Apply Layered Image Choreography",
            "added_layers": len(layers),
            "layer_ids": [item.id for item in layers],
            "composition": target.to_dict(),
        }

    def motion_ai_candidate_preview(
        self,
        *,
        composition_id: str,
        proposal: Mapping[str, Any],
        output_dir: str,
        times_ms: list[int] | None = None,
    ) -> dict[str, Any]:
        from pathlib import Path

        from app.motion_designer.ai_workspace import apply_motion_ai_proposal
        from app.motion_designer.export_renderer import MotionExportRenderer

        composition = self._motion_store().get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        candidate = apply_motion_ai_proposal(composition, proposal)
        duration = max(1, candidate.duration_ms)
        samples = times_ms or [0, duration // 2, max(0, duration - 1)]
        directory = Path(output_dir).expanduser().resolve()
        renderer = MotionExportRenderer()
        outputs = [
            renderer.save_png(
                candidate,
                min(duration, max(0, int(time_ms))),
                directory / f"candidate_{index:02d}_{int(time_ms):06d}ms.png",
            )
            for index, time_ms in enumerate(samples)
        ]
        return {
            "schema": "tigerstudio.motion.ai.candidate_preview.v1",
            "composition_id": composition_id,
            "base_revision": composition.revision,
            "frames": [str(item.resolve()) for item in outputs],
            "times_ms": [int(item) for item in samples],
        }

    def motion_ai_brief_create(
        self,
        *,
        composition_id: str,
        prompt: str = "",
        references: list[Mapping[str, Any]] | None = None,
        provider: str = "",
        decompose_images: bool = True,
        max_decomposed_elements: int = 5,
        segmentation_mode: str = "auto",
        inpaint_mode: str = "auto",
        reconstruct_text: bool = True,
        ocr_native_threshold: float = 0.78,
        motion_variant: str = "auto",
    ) -> dict[str, Any]:
        del (
            provider,
            decompose_images,
            max_decomposed_elements,
            segmentation_mode,
            inpaint_mode,
            reconstruct_text,
            ocr_native_threshold,
            motion_variant,
        )
        from app.motion_designer.ai_generation import build_deterministic_generation_plan

        composition = self._motion_store().get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        plan = build_deterministic_generation_plan(composition, prompt, references or [])
        return {
            "schema": "tigercapture.motion.ai.brief.v1",
            "composition_id": composition.id,
            "base_revision": composition.revision,
            "prompt": str(prompt or "").strip(),
            "brief": plan.brief.to_dict(),
            "warnings": list(plan.warnings),
        }

    def motion_ai_storyboard_generate(
        self,
        *,
        composition_id: str,
        prompt: str = "",
        references: list[Mapping[str, Any]] | None = None,
        provider: str = "",
        decompose_images: bool = True,
        max_decomposed_elements: int = 5,
        segmentation_mode: str = "auto",
        inpaint_mode: str = "auto",
        reconstruct_text: bool = True,
        ocr_native_threshold: float = 0.78,
        motion_variant: str = "auto",
    ) -> dict[str, Any]:
        proposal = self.motion_ai_candidate_generate(
            composition_id=composition_id,
            prompt=prompt,
            references=references,
            provider=provider,
            decompose_images=decompose_images,
            max_decomposed_elements=max_decomposed_elements,
            segmentation_mode=segmentation_mode,
            inpaint_mode=inpaint_mode,
            reconstruct_text=reconstruct_text,
            ocr_native_threshold=ocr_native_threshold,
            motion_variant=motion_variant,
        )
        analysis = proposal.get("analysis") if isinstance(proposal.get("analysis"), Mapping) else {}
        generation = analysis.get("generation_plan") if isinstance(analysis, Mapping) else {}
        return dict(generation or {})

    def motion_ai_candidate_generate(
        self,
        *,
        composition_id: str,
        prompt: str = "",
        references: list[Mapping[str, Any]] | None = None,
        provider: str = "",
        decompose_images: bool = True,
        max_decomposed_elements: int = 5,
        segmentation_mode: str = "auto",
        inpaint_mode: str = "auto",
        reconstruct_text: bool = True,
        ocr_native_threshold: float = 0.78,
        motion_variant: str = "auto",
    ) -> dict[str, Any]:
        from app.motion_designer.ai_generation import generate_motion_ai_proposal

        composition = self._motion_store().get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        return generate_motion_ai_proposal(
            composition,
            prompt,
            references or [],
            provider_id=provider or None,
            decompose_images=decompose_images,
            max_decomposed_elements=max_decomposed_elements,
            segmentation_mode=segmentation_mode,
            inpaint_mode=inpaint_mode,
            reconstruct_text=reconstruct_text,
            ocr_native_threshold=ocr_native_threshold,
            motion_variant=motion_variant,
        ).to_dict()

    def motion_ai_candidates_generate(
        self,
        *,
        composition_id: str,
        prompt: str = "",
        references: list[Mapping[str, Any]] | None = None,
        provider: str = "",
        decompose_images: bool = True,
        max_decomposed_elements: int = 5,
        segmentation_mode: str = "auto",
        inpaint_mode: str = "auto",
        reconstruct_text: bool = True,
        ocr_native_threshold: float = 0.78,
        motion_variant: str = "auto",
    ) -> dict[str, Any]:
        from app.motion_designer.ai_generation import generate_motion_ai_candidates

        composition = self._motion_store().get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        variants = (
            ("clean", "dynamic", "collage")
            if motion_variant == "auto"
            else (motion_variant,)
        )
        candidates = generate_motion_ai_candidates(
            composition,
            prompt,
            references or [],
            variants=variants,
            provider_id=provider or None,
            decompose_images=decompose_images,
            max_decomposed_elements=max_decomposed_elements,
            segmentation_mode=segmentation_mode,
            inpaint_mode=inpaint_mode,
            reconstruct_text=reconstruct_text,
            ocr_native_threshold=ocr_native_threshold,
        )
        return {
            "schema": "tigerstudio.motion.ai.candidate_set.v1",
            "selected_index": 0,
            "candidates": [item.to_dict() for item in candidates],
        }

    def motion_ai_patch_plan(
        self,
        *,
        composition_id: str,
        prompt: str,
        layer_ids: list[str] | None = None,
        provider: str = "",
    ) -> dict[str, Any]:
        from app.motion_designer.ai_generation import generate_motion_ai_patch

        composition = self._motion_store().get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        return generate_motion_ai_patch(
            composition,
            prompt,
            layer_ids or [],
            provider_id=provider or None,
        )

    def motion_ai_patch_apply(self, *, composition_id: str, patch: Mapping[str, Any]) -> dict[str, Any]:
        from app.motion_designer.ai_generation import apply_motion_ai_patch

        store = self._motion_store()
        composition = store.get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        candidate = apply_motion_ai_patch(composition, patch)
        changed = candidate.revision != composition.revision
        store[composition_id] = candidate
        if changed:
            self._motion_sync_owner()
        return {
            "changed": changed,
            "undo_label": "Apply Motion AI Patch",
            "composition": candidate.to_dict(),
            "operation_count": len(list(patch.get("operations") or [])),
        }


__all__ = ["MotionAIGenerationAdapterMixin"]
