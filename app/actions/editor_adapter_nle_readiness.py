"""NLE readiness, evidence, and real-project corpus adapter methods."""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


class NleReadinessAdapterMixin:
    """Adapter methods for NLE claim gates, evidence, and corpus registration."""

    def nle_real_corpus_status(self, *, manifest_path: str = "") -> dict[str, Any]:
        from app.nle_real_corpus import build_nle_real_project_corpus_report

        return build_nle_real_project_corpus_report(manifest_path=manifest_path or None)

    def nle_real_corpus_discover(
        self,
        *,
        search_roots: Sequence[str] | None = None,
        manifest_path: str = "",
        max_results: int = 40,
        max_depth: int = 5,
        allow_generated: bool = False,
    ) -> dict[str, Any]:
        from app.nle_real_corpus import discover_nle_real_project_candidates

        return discover_nle_real_project_candidates(
            search_roots=tuple(str(row) for row in (search_roots or ()) if str(row or "").strip()) or None,
            manifest_path=manifest_path or None,
            max_results=max(1, _int(max_results, 40)),
            max_depth=max(0, _int(max_depth, 5)),
            allow_generated=bool(allow_generated),
        )

    def nle_real_corpus_intake_board(
        self,
        *,
        search_roots: Sequence[str] | None = None,
        manifest_path: str = "",
        max_results: int = 20,
        max_depth: int = 5,
        allow_generated: bool = False,
    ) -> dict[str, Any]:
        from app.nle_real_corpus import build_nle_real_project_intake_board

        return build_nle_real_project_intake_board(
            search_roots=tuple(str(row) for row in (search_roots or ()) if str(row or "").strip()) or None,
            manifest_path=manifest_path or None,
            max_results=max(1, _int(max_results, 20)),
            max_depth=max(0, _int(max_depth, 5)),
            allow_generated=bool(allow_generated),
        )

    def nle_real_corpus_collection_kit(
        self,
        *,
        search_roots: Sequence[str] | None = None,
        manifest_path: str = "",
        max_results: int = 20,
        max_depth: int = 5,
        allow_generated: bool = False,
    ) -> dict[str, Any]:
        from app.nle_real_corpus import build_nle_real_project_collection_kit

        return build_nle_real_project_collection_kit(
            search_roots=tuple(str(row) for row in (search_roots or ()) if str(row or "").strip()) or None,
            manifest_path=manifest_path or None,
            max_results=max(1, _int(max_results, 20)),
            max_depth=max(0, _int(max_depth, 5)),
            allow_generated=bool(allow_generated),
        )

    def nle_real_corpus_gate_board(
        self,
        *,
        search_roots: Sequence[str] | None = None,
        manifest_path: str = "",
        max_results: int = 20,
        max_depth: int = 5,
        allow_generated: bool = False,
    ) -> dict[str, Any]:
        from app.nle_real_corpus import build_nle_real_project_gate_board

        return build_nle_real_project_gate_board(
            search_roots=tuple(str(row) for row in (search_roots or ()) if str(row or "").strip()) or None,
            manifest_path=manifest_path or None,
            max_results=max(1, _int(max_results, 20)),
            max_depth=max(0, _int(max_depth, 5)),
            allow_generated=bool(allow_generated),
        )

    def nle_real_corpus_workbench(
        self,
        *,
        search_roots: Sequence[str] | None = None,
        manifest_path: str = "",
        max_results: int = 20,
        max_depth: int = 5,
        allow_generated: bool = False,
    ) -> dict[str, Any]:
        from app.nle_real_corpus_workbench import build_nle_real_project_workbench

        return build_nle_real_project_workbench(
            search_roots=tuple(str(row) for row in (search_roots or ()) if str(row or "").strip()) or None,
            manifest_path=manifest_path or None,
            max_results=max(1, _int(max_results, 20)),
            max_depth=max(0, _int(max_depth, 5)),
            allow_generated=bool(allow_generated),
        )

    def nle_real_corpus_validation_plan(self, *, manifest_path: str = "") -> dict[str, Any]:
        from app.nle_real_corpus import build_nle_real_project_validation_plan

        return build_nle_real_project_validation_plan(manifest_path=manifest_path or None)

    def nle_real_corpus_validation_packet(
        self,
        *,
        project_id: str = "",
        project_path: str = "",
        manifest_path: str = "",
    ) -> dict[str, Any]:
        from app.nle_real_corpus import build_nle_real_project_validation_packet

        return build_nle_real_project_validation_packet(
            project_id=project_id,
            project_path=project_path or None,
            manifest_path=manifest_path or None,
        )

    def nle_real_corpus_validation_preflight(
        self,
        *,
        project_id: str = "",
        project_path: str = "",
        manifest_path: str = "",
    ) -> dict[str, Any]:
        from app.nle_real_corpus import build_nle_real_project_validation_preflight

        return build_nle_real_project_validation_preflight(
            project_id=project_id,
            project_path=project_path or None,
            manifest_path=manifest_path or None,
        )

    def nle_real_corpus_validation_report(self, *, manifest_path: str = "") -> dict[str, Any]:
        from app.nle_real_corpus import build_nle_real_project_validation_report

        return build_nle_real_project_validation_report(manifest_path=manifest_path or None)

    def nle_real_corpus_preview_validation_evidence(
        self,
        *,
        project_id: str = "",
        project_path: str = "",
        manifest_path: str = "",
        checks: Sequence[Any] | dict[str, Any] | None = None,
        notes: str = "",
        operator: str = "",
        evidence_path: str = "",
    ) -> dict[str, Any]:
        from app.nle_real_corpus import preview_nle_real_project_validation_evidence

        return preview_nle_real_project_validation_evidence(
            project_id=project_id,
            project_path=project_path or None,
            manifest_path=manifest_path or None,
            checks=checks or (),
            notes=notes,
            operator=operator,
            evidence_path=evidence_path or None,
        )

    def nle_real_corpus_register_validation_evidence(
        self,
        *,
        project_id: str = "",
        project_path: str = "",
        manifest_path: str = "",
        checks: Sequence[Any] | dict[str, Any] | None = None,
        notes: str = "",
        operator: str = "",
        evidence_path: str = "",
    ) -> dict[str, Any]:
        from app.nle_real_corpus import register_nle_real_project_validation_evidence

        return register_nle_real_project_validation_evidence(
            project_id=project_id,
            project_path=project_path or None,
            manifest_path=manifest_path or None,
            checks=checks or (),
            notes=notes,
            operator=operator,
            evidence_path=evidence_path or None,
        )

    def nle_real_corpus_register(
        self,
        *,
        project_path: str = "",
        manifest_path: str = "",
        label: str = "",
        notes: str = "",
        allow_generated: bool = False,
    ) -> dict[str, Any]:
        from app.nle_real_corpus import register_real_project

        path = str(project_path or "").strip()
        if not path:
            owner = self._require_owner()
            for attr in ("_project_path", "project_path", "current_project_path", "_last_project_path"):
                candidate = getattr(owner, attr, None)
                if candidate:
                    path = str(candidate)
                    break
        if not path:
            raise ValueError("project_path is required when the current project has not been saved")
        return register_real_project(
            Path(path),
            manifest_path=manifest_path or None,
            label=label,
            notes=notes,
            allow_generated=bool(allow_generated),
        )

    def nle_real_corpus_preview_register(
        self,
        *,
        project_path: str = "",
        manifest_path: str = "",
        label: str = "",
        notes: str = "",
        allow_generated: bool = False,
    ) -> dict[str, Any]:
        from app.nle_real_corpus import project_metrics

        path = str(project_path or "").strip()
        if not path:
            owner = self._require_owner()
            for attr in ("_project_path", "project_path", "current_project_path", "_last_project_path"):
                candidate = getattr(owner, attr, None)
                if candidate:
                    path = str(candidate)
                    break
        if not path:
            raise ValueError("project_path is required when the current project has not been saved")
        metrics = project_metrics(Path(path))
        generated = bool(metrics.get("generated_fixture_like"))
        would_register = bool(metrics.get("exists")) and bool(metrics.get("parse_ok")) and (not generated or bool(allow_generated))
        return {
            "schema": "tigerstudio.nle.real_project_corpus.preview_register.v1",
            "would_register": would_register,
            "project_path": str(Path(path)),
            "manifest_path": manifest_path,
            "label": label,
            "notes": notes,
            "allow_generated": bool(allow_generated),
            "metrics": metrics,
            "warnings": ["generated_fixture_rejected"] if generated and not allow_generated else [],
        }

    def nle_timeline_stress_status(self, *, report_path: str = "") -> dict[str, Any]:
        from app.nle_timeline_stress import build_nle_timeline_stress_report

        return build_nle_timeline_stress_report(report_path=report_path or None)

    def nle_core_action_coverage(self, *, action_ids: Sequence[str] | None = None) -> dict[str, Any]:
        from app.nle_core_actions import build_core_nle_action_coverage

        return build_core_nle_action_coverage(action_ids=action_ids)

    def nle_core_safety_matrix(self, *, action_ids: Sequence[str] | None = None) -> dict[str, Any]:
        from app.nle_polish_boards import build_nle_core_safety_matrix

        return build_nle_core_safety_matrix(action_ids=action_ids)

    def source_record_usability_board(self, *, action_ids: Sequence[str] | None = None) -> dict[str, Any]:
        from app.nle_polish_boards import build_source_record_usability_board

        return build_source_record_usability_board(action_ids=action_ids)

    def multicam_export_parity_board(self, *, action_ids: Sequence[str] | None = None) -> dict[str, Any]:
        from app.nle_polish_boards import build_multicam_export_parity_board

        return build_multicam_export_parity_board(self.snapshot(media_limit=500), action_ids=action_ids)

    def proxy_apply_review_board(self) -> dict[str, Any]:
        from app.nle_polish_boards import build_proxy_apply_review_board

        return build_proxy_apply_review_board(self.snapshot(media_limit=500))

    def conform_apply_review_board(self) -> dict[str, Any]:
        from app.nle_polish_boards import build_conform_apply_review_board

        return build_conform_apply_review_board(self.snapshot(media_limit=500))

    def undo_long_session_plan(self, *, action_ids: Sequence[str] | None = None) -> dict[str, Any]:
        from app.nle_polish_boards import build_undo_long_session_plan

        return build_undo_long_session_plan(action_ids=action_ids)

    def storyline_gesture_polish_board(self, *, action_ids: Sequence[str] | None = None) -> dict[str, Any]:
        from app.nle_polish_boards import build_storyline_gesture_polish_board

        return build_storyline_gesture_polish_board(action_ids=action_ids)

    def nle_undo_health(self, *, report_path: str = "") -> dict[str, Any]:
        from app.nle_timeline_stress import build_nle_undo_health_matrix

        return build_nle_undo_health_matrix(report_path=report_path or None)

    def nle_undo_review_board(self, *, report_path: str = "") -> dict[str, Any]:
        from app.nle_timeline_stress import build_nle_undo_review_board

        return build_nle_undo_review_board(report_path=report_path or None)

    def nle_undo_recovery_playbook(self, *, report_path: str = "") -> dict[str, Any]:
        from app.nle_timeline_stress import build_nle_undo_recovery_playbook

        return build_nle_undo_recovery_playbook(report_path=report_path or None)

    def nle_undo_stability_dashboard(self, *, report_path: str = "") -> dict[str, Any]:
        from app.nle_timeline_stress import build_nle_undo_stability_dashboard

        return build_nle_undo_stability_dashboard(report_path=report_path or None)

    def nle_evidence(self, *, action_ids: Sequence[str] | None = None) -> dict[str, Any]:
        from app.nle_evidence import build_nle_evidence_report

        snapshot = self.snapshot(media_limit=500)
        snapshot["nle_real_project_corpus"] = self.nle_real_corpus_status()
        snapshot["nle_timeline_stress"] = self.nle_timeline_stress_status()
        return build_nle_evidence_report(
            snapshot,
            action_ids=tuple(str(row) for row in (action_ids or ())),
            evidence_level="project_snapshot",
        )

    def professional_nle_readiness(
        self,
        *,
        action_count: int = 0,
        action_ids: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        from app.nle_readiness import build_nle_readiness_report, format_nle_readiness_summary

        snapshot = self.snapshot(media_limit=500)
        snapshot["nle_evidence"] = self.nle_evidence(action_ids=action_ids)
        report = build_nle_readiness_report(snapshot, action_count=max(0, _int(action_count, 0)))
        report["summary_text"] = format_nle_readiness_summary(report)
        return report

    def nle_target_gap(
        self,
        *,
        target_score: int = 95,
        action_count: int = 0,
        action_ids: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        from app.nle_target_gap import build_nle_target_gap_board

        report = self.professional_nle_readiness(
            action_count=action_count,
            action_ids=action_ids,
        )
        return build_nle_target_gap_board(
            report,
            target_score=max(0, _int(target_score, 95)),
            real_corpus_report=self.nle_real_corpus_status(),
        )


__all__ = ["NleReadinessAdapterMixin"]
