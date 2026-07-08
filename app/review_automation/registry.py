from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class ReviewFeature:
    id: str
    title: str
    category: str
    summary: str
    claim: str
    resource_ids: tuple[str, ...] = ()
    qa_reports: tuple[str, ...] = ()
    artifact_ids: tuple[str, ...] = ()
    status_hint: str = "implemented"
    priority: int = 50
    tags: tuple[str, ...] = ()
    guardrails: tuple[str, ...] = ()
    next_steps: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "summary": self.summary,
            "claim": self.claim,
            "resource_ids": list(self.resource_ids),
            "qa_reports": list(self.qa_reports),
            "artifact_ids": list(self.artifact_ids),
            "status_hint": self.status_hint,
            "priority": int(self.priority),
            "tags": list(self.tags),
            "guardrails": list(self.guardrails),
            "next_steps": list(self.next_steps),
        }


def default_review_features() -> tuple[ReviewFeature, ...]:
    return (
        ReviewFeature(
            id="overview_editor",
            title="Studio Overview",
            category="Core Editing",
            summary="A QA-backed editor overview showing import, timeline, preview, docks, and project restore evidence.",
            claim="TigerCapture can present a stable end-to-end editor workflow for review and introduction material.",
            resource_ids=("overview_screen_demo", "review_overview_poster"),
            qa_reports=("debugCapture/editor_e2e_smoke_report.json",),
            artifact_ids=("catalog_editor_surface", "catalog_timeline_detail", "editor_imported", "editor_contact_sheet", "review_overview_poster"),
            priority=10,
            tags=("overview", "qa", "screenshots"),
        ),
        ReviewFeature(
            id="screenstudio_auto_polish",
            title="Screen Studio Auto Polish",
            category="Creator Workflow",
            summary="Cursor sidecar and demo video evidence for auto zoom, click emphasis, and tutorial-style polish.",
            claim="Screen recording evidence can drive repeatable review captures for Auto Polish workflows.",
            resource_ids=("screenstudio_cursor_demo",),
            qa_reports=(
                "debugCapture/screenstudio_auto_polish_qa.json",
                "debugCapture/screenstudio_sidecar_intake_qa.json",
            ),
            artifact_ids=("screenstudio_cursor_demo", "screenstudio_cursor_gif"),
            priority=20,
            tags=("screenstudio", "cursor", "auto-polish"),
        ),
        ReviewFeature(
            id="ai_script_edit",
            title="AI Script Edit",
            category="AI Assistance",
            summary="Transcript fixture and corpus QA hooks for text-driven edit planning and review-safe AI demos.",
            claim="AI-assisted editing can be demonstrated from a controlled transcript without using private user media.",
            resource_ids=("ai_script_transcript_demo",),
            qa_reports=(
                "debugCapture/ai_edit_corpus_quality_qa.json",
                "debugCapture/ai_edit_corpus_intake_qa.json",
            ),
            artifact_ids=("ai_script_transcript_demo",),
            priority=30,
            tags=("ai", "transcript", "text-editing"),
            guardrails=("Local/fallback provider state must be shown when cloud AI is not configured.",),
        ),
        ReviewFeature(
            id="action_automation",
            title="AI/MCP Action Automation",
            category="Automation",
            summary="Headless action scenarios build a real edit state through the same registered action surface used by AI, MCP, QA, and developer tools.",
            claim="TigerCapture can prove scripted editor work without mouse clicks by producing scenario JSON and timeline storyboard evidence.",
            resource_ids=("overview_screen_demo", "dialogue_cleanup_demo"),
            qa_reports=(
                "debugCapture/automation_bridge_qa.json",
                "debugCapture/automation_mcp_qa.json",
            ),
            artifact_ids=("action_scenario_timeline", "action_scenario_youtube_frame", "action_scenario_report"),
            priority=35,
            tags=("automation", "mcp", "python-actions", "qa"),
            guardrails=("Use registered actions only; do not expose arbitrary Python or shell execution to review scenarios.",),
        ),
        ReviewFeature(
            id="multilingual_ui",
            title="Typography And Multilingual Text",
            category="Typography",
            summary="Large title layers, captions, and multilingual text samples are captured with CJK-safe fonts, title presets, and keyframed lanes.",
            claim="TigerCapture treats text as animated design material, not just a small subtitle overlay.",
            qa_reports=("debugCapture/localization_audit_qa.json",),
            priority=25,
            tags=("typography", "titles", "i18n", "localization", "multilingual"),
            guardrails=("Do not use a single tiny caption as typography evidence; show large title text, controls, and text lanes.",),
        ),
        ReviewFeature(
            id="live2d_overlay",
            title="Live2D Overlay Timeline",
            category="Actor Overlay",
            summary="Existing editor smoke evidence for loading actor lanes alongside normal video timeline content.",
            claim="Live2D overlay workflows can be included in review output when the editor smoke evidence is passing.",
            qa_reports=("debugCapture/editor_e2e_smoke_report.json",),
            artifact_ids=("editor_actor_project",),
            priority=45,
            tags=("live2d", "actor", "timeline"),
            guardrails=("Do not claim Spine rendering quality until the separate Spine renderer work is fixed.",),
        ),
        ReviewFeature(
            id="audio_cleanup",
            title="Dialogue And Audio Cleanup",
            category="Finishing",
            summary="Synthetic dialogue fixture for audio cleanup, voice workflow, and before/after review demos.",
            claim="Audio cleanup demos can run from deterministic local audio rather than user recordings.",
            resource_ids=("dialogue_cleanup_demo",),
            qa_reports=("debugCapture/color_audio_accuracy_qa.json",),
            artifact_ids=("dialogue_cleanup_demo",),
            priority=55,
            tags=("audio", "dialogue", "finishing"),
        ),
        ReviewFeature(
            id="review_site_deck",
            title="Review Site And Deck Generator",
            category="Automation",
            summary="Transforms feature evidence, screenshots, sample media, and spec fingerprints into HTML and PPT outputs.",
            claim="The review package can regenerate presentation material as specs and QA evidence change.",
            resource_ids=("review_overview_poster",),
            artifact_ids=("review_contact_sheet", "review_site", "review_deck"),
            priority=65,
            tags=("automation", "html", "ppt"),
        ),
    )


def _resource_ready(resource_id: str, resources_by_id: Mapping[str, Mapping[str, Any]]) -> bool:
    row = resources_by_id.get(resource_id)
    return bool(row and row.get("ready"))


def _report_ok(raw_path: str, project_root: Path) -> bool | None:
    path = project_root / raw_path
    if not path.exists():
        return None
    try:
        import json

        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    if not isinstance(payload, dict):
        return False
    return bool(payload.get("ok", True))


def evaluate_review_features(
    features: Iterable[ReviewFeature],
    *,
    sample_report: Mapping[str, Any],
    project_root: str | Path,
) -> list[dict[str, Any]]:
    root = Path(project_root)
    resources = list(sample_report.get("resources", []) or [])
    resources_by_id = {
        str(row.get("id")): row
        for row in resources
        if isinstance(row, Mapping) and row.get("id")
    }
    evaluated: list[dict[str, Any]] = []
    for feature in sorted(features, key=lambda item: (item.priority, item.id)):
        missing_resources = [
            resource_id
            for resource_id in feature.resource_ids
            if not _resource_ready(resource_id, resources_by_id)
        ]
        qa_states = {raw_path: _report_ok(raw_path, root) for raw_path in feature.qa_reports}
        missing_reports = [path for path, state in qa_states.items() if state is None]
        failing_reports = [path for path, state in qa_states.items() if state is False]
        if feature.status_hint in {"blocked", "planned"}:
            status = feature.status_hint
        elif missing_resources:
            status = "blocked"
        elif failing_reports:
            status = "blocked"
        elif missing_reports:
            status = "implemented"
        else:
            status = "evidence_ready"
        row = feature.to_dict()
        row.update(
            {
                "status": status,
                "missing_resources": missing_resources,
                "missing_reports": missing_reports,
                "failing_reports": failing_reports,
                "qa_states": qa_states,
            }
        )
        evaluated.append(row)
    return evaluated
