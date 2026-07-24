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

    def motion_ai_brief_create(
        self,
        *,
        composition_id: str,
        prompt: str = "",
        references: list[Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
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
    ) -> dict[str, Any]:
        proposal = self.motion_ai_candidate_generate(
            composition_id=composition_id,
            prompt=prompt,
            references=references,
            provider=provider,
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
        ).to_dict()

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
