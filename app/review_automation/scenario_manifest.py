from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class ReviewScenario:
    id: str
    feature_id: str
    title: str
    mode: str
    summary: str
    sample_resource_ids: tuple[str, ...] = ()
    action_ids: tuple[str, ...] = ()
    capture_targets: tuple[str, ...] = ()
    artifact_ids: tuple[str, ...] = ()
    qa_reports: tuple[str, ...] = ()
    fallback: str = ""
    tags: tuple[str, ...] = ()
    guardrails: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "feature_id": self.feature_id,
            "title": self.title,
            "mode": self.mode,
            "summary": self.summary,
            "sample_resource_ids": list(self.sample_resource_ids),
            "action_ids": list(self.action_ids),
            "capture_targets": list(self.capture_targets),
            "artifact_ids": list(self.artifact_ids),
            "qa_reports": list(self.qa_reports),
            "fallback": self.fallback,
            "tags": list(self.tags),
            "guardrails": list(self.guardrails),
        }


def default_review_scenarios() -> tuple[ReviewScenario, ...]:
    return (
        ReviewScenario(
            id="overview_editor_ui",
            feature_id="overview_editor",
            title="Editor overview UI capture",
            mode="ui_capture",
            summary="Use the editor E2E smoke capture and public crops as the stable product overview evidence.",
            sample_resource_ids=("overview_screen_demo", "review_overview_poster"),
            action_ids=("media.import_to_timeline", "timeline.set_zoom", "capture.screenshot"),
            capture_targets=("editor", "timeline"),
            artifact_ids=("catalog_editor_surface", "catalog_timeline_detail", "editor_imported", "review_overview_poster"),
            qa_reports=("debugCapture/editor_e2e_smoke_report.json",),
            fallback="Use catalog crops from the last passing editor smoke run.",
            tags=("overview", "ui", "timeline"),
        ),
        ReviewScenario(
            id="screenstudio_auto_polish_sample",
            feature_id="screenstudio_auto_polish",
            title="Screen Studio auto-polish sample",
            mode="sample_media",
            summary="Use an imported YouTube sample clip plus cursor sidecar metadata to produce GIF/video evidence.",
            sample_resource_ids=("screenstudio_cursor_demo",),
            action_ids=("media.import_to_timeline", "capture.gif"),
            capture_targets=("timeline", "preview"),
            artifact_ids=("screenstudio_cursor_demo", "screenstudio_cursor_gif"),
            qa_reports=("debugCapture/screenstudio_auto_polish_qa.json", "debugCapture/screenstudio_sidecar_intake_qa.json"),
            fallback="Keep a generated cursor-sidecar fixture visible until real interaction corpus is ready.",
            tags=("screenstudio", "cursor", "gif"),
        ),
        ReviewScenario(
            id="ai_script_edit_fixture",
            feature_id="ai_script_edit",
            title="AI script-edit fixture review",
            mode="fixture_review",
            summary="Use the controlled transcript fixture and AI corpus QA reports for safe text-editing claims.",
            sample_resource_ids=("ai_script_transcript_demo",),
            action_ids=("project.snapshot", "review.scenario.run"),
            artifact_ids=("ai_script_transcript_demo",),
            qa_reports=("debugCapture/ai_edit_corpus_quality_qa.json", "debugCapture/ai_edit_corpus_intake_qa.json"),
            fallback="Block marketing language when real corpus intake is insufficient.",
            tags=("ai", "transcript", "guardrail"),
            guardrails=("Do not claim smart automatic editing quality without real corpus evidence.",),
        ),
        ReviewScenario(
            id="action_automation_headless",
            feature_id="action_automation",
            title="Registered action headless edit",
            mode="headless_action",
            summary="Build an edit timeline through registered actions and emit scenario JSON plus a storyboard image.",
            sample_resource_ids=("overview_screen_demo", "dialogue_cleanup_demo"),
            action_ids=(
                "media.import_to_timeline",
                "timeline.set_zoom",
                "timeline.marker.add",
                "timeline.split",
                "clip.set_filter",
                "clip.set_color_grade",
                "node.add",
                "text.add",
                "text.set_keyframes",
                "clip.set_speed",
                "clip.set_fade",
                "audio.track.set_volume",
                "audio.track.set_pan",
                "audio.track.mute",
                "audio.track.solo",
                "audio.mixer.state",
                "audio.clip.set_gain",
            ),
            capture_targets=("headless_storyboard",),
            artifact_ids=("action_scenario_timeline", "action_scenario_youtube_frame", "action_scenario_report"),
            qa_reports=("debugCapture/automation_bridge_qa.json", "debugCapture/automation_mcp_qa.json"),
            fallback="If live UI capture is unavailable, keep the headless storyboard as traceable evidence.",
            tags=("actions", "mcp", "headless"),
            guardrails=("Only registered actions are allowed; arbitrary Python/shell is not review evidence.",),
        ),
        ReviewScenario(
            id="live2d_actor_lane_smoke",
            feature_id="live2d_overlay",
            title="Live2D actor lane smoke",
            mode="ui_capture",
            summary="Use editor smoke evidence that actor lanes can coexist with normal video timeline content.",
            action_ids=("actor.add", "actor.set_transform", "actor.set_keyframes", "capture.screenshot"),
            capture_targets=("editor", "actor_lane"),
            artifact_ids=("editor_actor_project",),
            qa_reports=("debugCapture/editor_e2e_smoke_report.json",),
            fallback="Show actor-lane data-model evidence only if live renderer capture is unavailable.",
            tags=("live2d", "actor", "timeline"),
            guardrails=("Do not use this scenario to claim Spine render correctness.",),
        ),
        ReviewScenario(
            id="audio_cleanup_fixture",
            feature_id="audio_cleanup",
            title="Dialogue cleanup fixture",
            mode="fixture_review",
            summary="Use deterministic dialogue audio to demonstrate repeatable audio cleanup review input.",
            sample_resource_ids=("dialogue_cleanup_demo",),
            action_ids=(
                "media.import_to_timeline",
                "audio.track.set_volume",
                "audio.track.set_pan",
                "audio.track.mute",
                "audio.track.solo",
                "audio.mixer.state",
                "audio.clip.set_gain",
            ),
            capture_targets=("audio_track",),
            artifact_ids=("dialogue_cleanup_demo",),
            qa_reports=("debugCapture/color_audio_accuracy_qa.json",),
            tags=("audio", "dialogue", "fixture"),
        ),
        ReviewScenario(
            id="review_site_deck_render",
            feature_id="review_site_deck",
            title="Review site and deck render",
            mode="renderer",
            summary="Render the evidence graph into HTML feature pages and summary/detailed/evidence-full PPTX decks.",
            sample_resource_ids=("review_overview_poster",),
            action_ids=("review.scenario.run",),
            capture_targets=("html", "pptx"),
            artifact_ids=("review_contact_sheet", "review_site", "review_deck", "evidence_graph"),
            tags=("html", "pptx", "renderer"),
        ),
        ReviewScenario(
            id="multilingual_runtime_audit",
            feature_id="multilingual_ui",
            title="Runtime locale audit",
            mode="qa_report",
            summary="Use locale QA to prove six-language runtime coverage and font-safe review output.",
            qa_reports=("debugCapture/localization_audit_qa.json",),
            tags=("i18n", "qa", "font"),
        ),
    )


def _resource_ready(resource_id: str, resources_by_id: Mapping[str, Mapping[str, Any]]) -> bool:
    row = resources_by_id.get(resource_id)
    return bool(row and row.get("ready"))


def _artifact_ready(artifact_id: str, artifacts_by_id: Mapping[str, Mapping[str, Any]]) -> bool:
    row = artifacts_by_id.get(artifact_id)
    return bool(row and row.get("exists"))


def evaluate_review_scenarios(
    scenarios: Iterable[ReviewScenario],
    *,
    sample_report: Mapping[str, Any],
    artifacts: Iterable[Mapping[str, Any]],
    features: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    resources_by_id = {
        str(row.get("id")): row
        for row in list(sample_report.get("resources", []) or [])
        if isinstance(row, Mapping) and row.get("id")
    }
    artifacts_by_id = {
        str(row.get("id")): row
        for row in list(artifacts or [])
        if isinstance(row, Mapping) and row.get("id")
    }
    features_by_id = {
        str(row.get("id")): row
        for row in list(features or [])
        if isinstance(row, Mapping) and row.get("id")
    }
    rows: list[dict[str, Any]] = []
    for scenario in scenarios:
        data = scenario.to_dict()
        feature = features_by_id.get(scenario.feature_id, {})
        missing_resources = [
            resource_id
            for resource_id in scenario.sample_resource_ids
            if not _resource_ready(resource_id, resources_by_id)
        ]
        missing_artifacts = [
            artifact_id
            for artifact_id in scenario.artifact_ids
            if not _artifact_ready(artifact_id, artifacts_by_id)
        ]
        feature_status = str(feature.get("status") or "unknown")
        if feature_status == "blocked":
            status = "blocked"
        elif missing_resources or missing_artifacts:
            status = "pending_evidence"
        elif scenario.mode == "headless_action":
            status = "action_ready"
        elif scenario.mode in {"ui_capture", "sample_media"}:
            status = "captured"
        else:
            status = "evidence_ready"
        data.update(
            {
                "status": status,
                "feature_status": feature_status,
                "missing_resources": missing_resources,
                "missing_artifacts": missing_artifacts,
                "ready_resource_count": len(scenario.sample_resource_ids) - len(missing_resources),
                "ready_artifact_count": len(scenario.artifact_ids) - len(missing_artifacts),
            }
        )
        rows.append(data)
    return rows
