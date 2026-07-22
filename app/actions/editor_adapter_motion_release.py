"""Motion product release-gate actions."""
from __future__ import annotations

from typing import Any, Mapping

from app.motion_designer.release_acceptance import motion_release_preflight, validate_release_evidence


class MotionReleaseAdapterMixin:
    def motion_release_evidence_validate(self, *, evidence: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return validate_release_evidence(evidence)

    def motion_release_preflight(self, *, composition_id: str, profile_id: str = "",
                                 output_path: str = "", fps: float | None = None,
                                 gpu_diagnostics: Mapping[str, Any] | None = None,
                                 evidence: Mapping[str, Any] | None = None) -> dict[str, Any]:
        composition = self._motion_store().get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        return motion_release_preflight(
            composition, profile_id=profile_id, output_path=output_path, fps=fps,
            gpu_diagnostics=gpu_diagnostics, evidence=evidence,
        )


__all__ = ["MotionReleaseAdapterMixin"]
