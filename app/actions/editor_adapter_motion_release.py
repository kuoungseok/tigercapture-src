"""Motion product release-gate actions."""
from __future__ import annotations

from typing import Any, Mapping

from app.motion_designer.performance_gate import run_motion_performance_gate
from app.motion_designer.release_acceptance import motion_release_preflight, validate_release_evidence


class MotionReleaseAdapterMixin:
    def motion_performance_gate(self, *, composition_id: str,
                                sample_times_ms: list[float] | None = None,
                                iterations: int = 3, width: int | None = None,
                                height: int | None = None, max_p95_ms: float = 0.0,
                                require_gpu: bool = False,
                                cache_max_bytes: int = 64 * 1024 * 1024,
                                template_ids: list[str] | None = None,
                                template_switch_iterations: int = 0) -> dict[str, Any]:
        composition = self._motion_store().get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        return run_motion_performance_gate(
            composition,
            sample_times_ms=sample_times_ms,
            iterations=iterations,
            width=width,
            height=height,
            max_p95_ms=max_p95_ms,
            require_gpu=require_gpu,
            cache_max_bytes=cache_max_bytes,
            template_ids=template_ids or (),
            template_switch_iterations=template_switch_iterations,
        )

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
